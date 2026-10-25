"""
AWS Housekeeping Checks
Each check returns a list of findings: {id, title, resource_id, details, action, severity}
"""

import json
from datetime import datetime, timezone, timedelta

import boto3
import botocore.exceptions


SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"


def safe_check(fn, category):
    """Wrap a check function and handle permission errors gracefully."""
    try:
        return fn()
    except botocore.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("AccessDenied", "AccessDeniedException", "AuthorizationError",
                    "UnauthorizedAccess", "NoCredentialProviders"):
            return [{
                "category": category,
                "severity": "INFO",
                "title": "Insufficient Permissions",
                "resource_id": "N/A",
                "details": f"Access denied for {category} checks: {code}",
                "action": "Grant ReadOnlyAccess to the SSO role to enable this check.",
            }]
        raise
    except Exception as e:
        return [{
            "category": category,
            "severity": "INFO",
            "title": "Check Error",
            "resource_id": "N/A",
            "details": str(e),
            "action": "Review error and retry.",
        }]


# ─── EC2 ─────────────────────────────────────────────────────────────────────

def check_stopped_ec2(session, region):
    def _check():
        findings = []
        ec2 = session.client("ec2", region_name=region)
        response = ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                state_reason = instance.get("StateTransitionReason", "")
                name_tag = next((t["Value"] for t in instance.get("Tags", []) if t["Key"] == "Name"), "N/A")
                findings.append({
                    "category": "EC2",
                    "severity": SEVERITY_MEDIUM,
                    "title": "Stopped EC2 Instance",
                    "resource_id": instance["InstanceId"],
                    "details": f"Name: {name_tag} | Type: {instance.get('InstanceType')} | Stopped: {state_reason}",
                    "action": "Terminate or start the instance. Stopped instances still incur EBS storage costs.",
                })
        return findings
    return safe_check(_check, "EC2")


def check_unattached_ebs(session, region):
    def _check():
        findings = []
        ec2 = session.client("ec2", region_name=region)
        response = ec2.describe_volumes(
            Filters=[{"Name": "status", "Values": ["available"]}]
        )
        for vol in response.get("Volumes", []):
            name_tag = next((t["Value"] for t in vol.get("Tags", []) if t["Key"] == "Name"), "N/A")
            size_gb = vol.get("Size", 0)
            findings.append({
                "category": "EC2",
                "severity": SEVERITY_MEDIUM,
                "title": "Unattached EBS Volume",
                "resource_id": vol["VolumeId"],
                "details": f"Name: {name_tag} | Size: {size_gb} GiB | Type: {vol.get('VolumeType')} | AZ: {vol.get('AvailabilityZone')}",
                "action": "Delete the volume if no longer needed. Snapshot it first if data must be preserved.",
            })
        return findings
    return safe_check(_check, "EC2")


def check_unused_elastic_ips(session, region):
    def _check():
        findings = []
        ec2 = session.client("ec2", region_name=region)
        response = ec2.describe_addresses()
        for addr in response.get("Addresses", []):
            if not addr.get("AssociationId"):
                findings.append({
                    "category": "EC2",
                    "severity": SEVERITY_LOW,
                    "title": "Unused Elastic IP",
                    "resource_id": addr.get("AllocationId", addr.get("PublicIp")),
                    "details": f"IP: {addr.get('PublicIp')} — not associated with any instance.",
                    "action": "Release the Elastic IP to avoid idle IP charges.",
                })
        return findings
    return safe_check(_check, "EC2")


# ─── IAM ─────────────────────────────────────────────────────────────────────

def check_iam_mfa(session, region):
    def _check():
        findings = []
        iam = session.client("iam")
        paginator = iam.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page["Users"]:
                mfa = iam.list_mfa_devices(UserName=user["UserName"])
                if not mfa["MFADevices"]:
                    findings.append({
                        "category": "IAM",
                        "severity": SEVERITY_HIGH,
                        "title": "IAM User Without MFA",
                        "resource_id": user["UserName"],
                        "details": f"User: {user['UserName']} | Created: {user['CreateDate'].strftime('%Y-%m-%d')}",
                        "action": "Enable MFA for this user immediately to secure the account.",
                    })
        return findings
    return safe_check(_check, "IAM")


def check_old_access_keys(session, region):
    def _check():
        findings = []
        iam = session.client("iam")
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        paginator = iam.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page["Users"]:
                keys = iam.list_access_keys(UserName=user["UserName"])
                for key in keys["AccessKeyMetadata"]:
                    if key["Status"] == "Active" and key["CreateDate"] < cutoff:
                        age_days = (datetime.now(timezone.utc) - key["CreateDate"]).days
                        findings.append({
                            "category": "IAM",
                            "severity": SEVERITY_HIGH,
                            "title": "Old IAM Access Key (>90 days)",
                            "resource_id": key["AccessKeyId"],
                            "details": f"User: {user['UserName']} | Key age: {age_days} days | Created: {key['CreateDate'].strftime('%Y-%m-%d')}",
                            "action": "Rotate this access key. Keys older than 90 days are a security risk.",
                        })
        return findings
    return safe_check(_check, "IAM")


def check_inactive_users(session, region):
    def _check():
        findings = []
        iam = session.client("iam")
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        paginator = iam.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page["Users"]:
                last_used = user.get("PasswordLastUsed")
                if last_used is None:
                    # Never logged in
                    created = user["CreateDate"]
                    if created < cutoff:
                        findings.append({
                            "category": "IAM",
                            "severity": SEVERITY_MEDIUM,
                            "title": "Inactive IAM User (Never Logged In)",
                            "resource_id": user["UserName"],
                            "details": f"Created: {created.strftime('%Y-%m-%d')} | Never logged in via console.",
                            "action": "Review and disable or delete this unused user account.",
                        })
                elif last_used < cutoff:
                    days_inactive = (datetime.now(timezone.utc) - last_used).days
                    findings.append({
                        "category": "IAM",
                        "severity": SEVERITY_MEDIUM,
                        "title": "Inactive IAM User (>90 days)",
                        "resource_id": user["UserName"],
                        "details": f"Last login: {last_used.strftime('%Y-%m-%d')} | Inactive for {days_inactive} days.",
                        "action": "Disable or delete this stale user account.",
                    })
        return findings
    return safe_check(_check, "IAM")


# ─── S3 ──────────────────────────────────────────────────────────────────────

def check_s3_public_access(session, region):
    def _check():
        findings = []
        s3 = session.client("s3")
        buckets = s3.list_buckets().get("Buckets", [])
        for bucket in buckets:
            bname = bucket["Name"]
            try:
                pab = s3.get_public_access_block(Bucket=bname)
                cfg = pab["PublicAccessBlockConfiguration"]
                if not all([
                    cfg.get("BlockPublicAcls"),
                    cfg.get("IgnorePublicAcls"),
                    cfg.get("BlockPublicPolicy"),
                    cfg.get("RestrictPublicBuckets"),
                ]):
                    findings.append({
                        "category": "S3",
                        "severity": SEVERITY_HIGH,
                        "title": "S3 Bucket with Public Access Not Fully Blocked",
                        "resource_id": bname,
                        "details": f"BlockPublicAcls={cfg.get('BlockPublicAcls')} | BlockPublicPolicy={cfg.get('BlockPublicPolicy')} | RestrictPublicBuckets={cfg.get('RestrictPublicBuckets')}",
                        "action": "Enable all 4 Block Public Access settings on this bucket unless it intentionally serves public content.",
                    })
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration":
                    findings.append({
                        "category": "S3",
                        "severity": SEVERITY_HIGH,
                        "title": "S3 Bucket with No Public Access Block Config",
                        "resource_id": bname,
                        "details": "No Public Access Block configuration found. Bucket may be publicly accessible.",
                        "action": "Configure Block Public Access settings for this bucket.",
                    })
        return findings
    return safe_check(_check, "S3")


def check_s3_versioning(session, region):
    def _check():
        findings = []
        s3 = session.client("s3")
        buckets = s3.list_buckets().get("Buckets", [])
        for bucket in buckets:
            bname = bucket["Name"]
            try:
                v = s3.get_bucket_versioning(Bucket=bname)
                status = v.get("Status", "Disabled")
                if status != "Enabled":
                    findings.append({
                        "category": "S3",
                        "severity": SEVERITY_LOW,
                        "title": "S3 Bucket Without Versioning",
                        "resource_id": bname,
                        "details": f"Versioning status: {status}",
                        "action": "Enable versioning for data protection and accidental deletion recovery.",
                    })
            except Exception:
                pass
        return findings
    return safe_check(_check, "S3")


# ─── Security Groups ─────────────────────────────────────────────────────────

def check_open_security_groups(session, region):
    def _check():
        findings = []
        ec2 = session.client("ec2", region_name=region)
        sgs = ec2.describe_security_groups().get("SecurityGroups", [])
        risky_ports = {22: "SSH", 3389: "RDP", 5432: "PostgreSQL", 3306: "MySQL", 1433: "MSSQL"}
        open_cidrs = {"0.0.0.0/0", "::/0"}
        for sg in sgs:
            for perm in sg.get("IpPermissions", []):
                from_port = perm.get("FromPort", 0)
                to_port = perm.get("ToPort", 65535)
                all_ranges = [r["CidrIp"] for r in perm.get("IpRanges", [])] + \
                             [r["CidrIpv6"] for r in perm.get("Ipv6Ranges", [])]
                for cidr in all_ranges:
                    if cidr in open_cidrs:
                        for port, proto_name in risky_ports.items():
                            if from_port <= port <= to_port:
                                sg_name = sg.get("GroupName", "N/A")
                                findings.append({
                                    "category": "Security Groups",
                                    "severity": SEVERITY_HIGH,
                                    "title": f"Security Group Open to World on {proto_name} (port {port})",
                                    "resource_id": sg["GroupId"],
                                    "details": f"SG Name: {sg_name} | VPC: {sg.get('VpcId')} | CIDR: {cidr} | Port: {port}",
                                    "action": f"Restrict inbound {proto_name} to specific IP ranges or use a VPN/bastion host.",
                                })
        return findings
    return safe_check(_check, "Security Groups")


def check_unused_security_groups(session, region):
    def _check():
        findings = []
        ec2 = session.client("ec2", region_name=region)
        all_sgs = {sg["GroupId"]: sg for sg in ec2.describe_security_groups().get("SecurityGroups", [])}

        # Collect used SG IDs from ENIs
        used_sg_ids = set()
        enis = ec2.describe_network_interfaces().get("NetworkInterfaces", [])
        for eni in enis:
            for sg in eni.get("Groups", []):
                used_sg_ids.add(sg["GroupId"])

        for sg_id, sg in all_sgs.items():
            if sg_id not in used_sg_ids and sg.get("GroupName") != "default":
                findings.append({
                    "category": "Security Groups",
                    "severity": SEVERITY_LOW,
                    "title": "Unused Security Group",
                    "resource_id": sg_id,
                    "details": f"Name: {sg.get('GroupName')} | VPC: {sg.get('VpcId')} — not attached to any ENI.",
                    "action": "Delete unused security groups to reduce complexity and blast radius.",
                })
        return findings
    return safe_check(_check, "Security Groups")


# ─── VPC ─────────────────────────────────────────────────────────────────────

def check_vpc_flow_logs(session, region):
    def _check():
        findings = []
        ec2 = session.client("ec2", region_name=region)
        vpcs = ec2.describe_vpcs().get("Vpcs", [])
        for vpc in vpcs:
            vpc_id = vpc["VpcId"]
            flow_logs = ec2.describe_flow_logs(
                Filters=[{"Name": "resource-id", "Values": [vpc_id]}]
            ).get("FlowLogs", [])
            if not flow_logs:
                name_tag = next((t["Value"] for t in vpc.get("Tags", []) if t["Key"] == "Name"), vpc_id)
                findings.append({
                    "category": "VPC",
                    "severity": SEVERITY_MEDIUM,
                    "title": "VPC Flow Logs Disabled",
                    "resource_id": vpc_id,
                    "details": f"Name: {name_tag} | CIDR: {vpc.get('CidrBlock')} — no flow logs configured for this VPC.",
                    "action": "Enable VPC Flow Logs for better network visibility and security auditing.",
                })
        return findings
    return safe_check(_check, "VPC")


def check_default_vpc(session, region):
    def _check():
        findings = []
        ec2 = session.client("ec2", region_name=region)
        vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}]).get("Vpcs", [])
        for vpc in vpcs:
            vpc_id = vpc["VpcId"]
            reservations = ec2.describe_instances(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}, {"Name": "instance-state-name", "Values": ["running"]}]
            ).get("Reservations", [])
            if reservations:
                findings.append({
                    "category": "VPC",
                    "severity": SEVERITY_LOW,
                    "title": "Default VPC in Use",
                    "resource_id": vpc_id,
                    "details": "The default VPC is being used for running instances. This is often against production best practices.",
                    "action": "Migrate workloads to a custom VPC with a well-defined CIDR and subnet structure.",
                })
        return findings
    return safe_check(_check, "VPC")


def check_unused_nat_gateways(session, region):
    def _check():
        findings = []
        ec2 = session.client("ec2", region_name=region)
        cw  = session.client("cloudwatch", region_name=region)
        nats = ec2.describe_nat_gateways(Filters=[{"Name": "state", "Values": ["available"]}]).get("NatGateways", [])
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        for nat in nats:
            nat_id = nat["NatGatewayId"]
            metrics = cw.get_metric_statistics(
                Namespace="AWS/NATGateway",
                MetricName="ActiveConnectionCount",
                Dimensions=[{"Name": "NatGatewayId", "Value": nat_id}],
                StartTime=start, EndTime=end,
                Period=604800, Statistics=["Maximum"],
            )
            max_conn = sum(d["Maximum"] for d in metrics.get("Datapoints", []))
            if max_conn == 0:
                findings.append({
                    "category": "VPC",
                    "severity": SEVERITY_MEDIUM,
                    "title": "Unused NAT Gateway",
                    "resource_id": nat_id,
                    "details": f"VPC: {nat.get('VpcId')} | Subnet: {nat.get('SubnetId')} — no active connections in the last 7 days.",
                    "action": "Delete the NAT Gateway to save costs (~$32/month base charge).",
                })
        return findings
    return safe_check(_check, "VPC")



# ─── RDS ─────────────────────────────────────────────────────────────────────

def check_stopped_rds(session, region):
    def _check():
        findings = []
        rds = session.client("rds", region_name=region)
        instances = rds.describe_db_instances().get("DBInstances", [])
        for db in instances:
            if db["DBInstanceStatus"] == "stopped":
                findings.append({
                    "category": "RDS",
                    "severity": SEVERITY_MEDIUM,
                    "title": "Stopped RDS Instance",
                    "resource_id": db["DBInstanceIdentifier"],
                    "details": f"Engine: {db['Engine']} {db.get('EngineVersion')} | Class: {db['DBInstanceClass']}",
                    "action": "Delete or start the instance. Stopped RDS instances still incur storage costs and resume automatically after 7 days.",
                })
        return findings
    return safe_check(_check, "RDS")


def check_public_rds(session, region):
    def _check():
        findings = []
        rds = session.client("rds", region_name=region)
        instances = rds.describe_db_instances().get("DBInstances", [])
        for db in instances:
            if db.get("PubliclyAccessible"):
                findings.append({
                    "category": "RDS",
                    "severity": SEVERITY_HIGH,
                    "title": "Publicly Accessible RDS Instance",
                    "resource_id": db["DBInstanceIdentifier"],
                    "details": f"Engine: {db['Engine']} | Class: {db['DBInstanceClass']} | Endpoint: {db.get('Endpoint', {}).get('Address', 'N/A')}",
                    "action": "Disable 'Publicly Accessible'. Use a VPN or bastion host to access RDS instances.",
                })
        return findings
    return safe_check(_check, "RDS")


# ─── ELB ─────────────────────────────────────────────────────────────────────

def check_idle_load_balancers(session, region):
    def _check():
        findings = []
        elbv2 = session.client("elbv2", region_name=region)
        lbs = elbv2.describe_load_balancers().get("LoadBalancers", [])
        for lb in lbs:
            lb_arn = lb["LoadBalancerArn"]
            tgs = elbv2.describe_target_groups(LoadBalancerArn=lb_arn).get("TargetGroups", [])
            healthy = 0
            for tg in tgs:
                health = elbv2.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])
                healthy += sum(
                    1 for t in health["TargetHealthDescriptions"]
                    if t["TargetHealth"]["State"] == "healthy"
                )
            if healthy == 0:
                findings.append({
                    "category": "ELB",
                    "severity": SEVERITY_MEDIUM,
                    "title": "Load Balancer with No Healthy Targets",
                    "resource_id": lb["LoadBalancerName"],
                    "details": f"Type: {lb['Type']} | DNS: {lb['DNSName']} | Target Groups: {len(tgs)}",
                    "action": "Review and delete idle load balancers to avoid unnecessary costs.",
                })
        return findings
    return safe_check(_check, "ELB")


# ─── Lambda ──────────────────────────────────────────────────────────────────

def check_lambda_errors(session, region):
    def _check():
        findings = []
        lam = session.client("lambda", region_name=region)
        cw = session.client("cloudwatch", region_name=region)
        paginator = lam.get_paginator("list_functions")
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        for page in paginator.paginate():
            for fn in page["Functions"]:
                fname = fn["FunctionName"]
                invocations = cw.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Invocations",
                    Dimensions=[{"Name": "FunctionName", "Value": fname}],
                    StartTime=start, EndTime=end,
                    Period=604800, Statistics=["Sum"],
                )
                errors = cw.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Errors",
                    Dimensions=[{"Name": "FunctionName", "Value": fname}],
                    StartTime=start, EndTime=end,
                    Period=604800, Statistics=["Sum"],
                )
                inv_count = sum(d["Sum"] for d in invocations.get("Datapoints", []))
                err_count = sum(d["Sum"] for d in errors.get("Datapoints", []))
                if inv_count > 0:
                    error_rate = (err_count / inv_count) * 100
                    if error_rate > 5:
                        findings.append({
                            "category": "Lambda",
                            "severity": SEVERITY_MEDIUM,
                            "title": "Lambda Function with High Error Rate",
                            "resource_id": fname,
                            "details": f"Error rate: {error_rate:.1f}% ({int(err_count)}/{int(inv_count)} invocations in last 7 days) | Runtime: {fn.get('Runtime')}",
                            "action": "Investigate CloudWatch Logs for this function. Review error patterns and fix root causes.",
                        })
        return findings
    return safe_check(_check, "Lambda")


# ─── CloudWatch ──────────────────────────────────────────────────────────────

def check_cloudwatch_alarms(session, region):
    def _check():
        findings = []
        cw = session.client("cloudwatch", region_name=region)
        paginator = cw.get_paginator("describe_alarms")
        for page in paginator.paginate(StateValue="INSUFFICIENT_DATA"):
            for alarm in page["MetricAlarms"]:
                findings.append({
                    "category": "CloudWatch",
                    "severity": SEVERITY_LOW,
                    "title": "CloudWatch Alarm in INSUFFICIENT_DATA State",
                    "resource_id": alarm["AlarmName"],
                    "details": f"Metric: {alarm.get('MetricName')} | Namespace: {alarm.get('Namespace')} | Last updated: {alarm['StateUpdatedTimestamp'].strftime('%Y-%m-%d')}",
                    "action": "Review alarm configuration. INSUFFICIENT_DATA may indicate the metric is no longer being published.",
                })
        return findings
    return safe_check(_check, "CloudWatch")


# ─── EKS ─────────────────────────────────────────────────────────────────────

def check_eks_node_groups(session, region):
    def _check():
        findings = []
        eks = session.client("eks", region_name=region)
        clusters = eks.list_clusters().get("clusters", [])
        for cluster_name in clusters:
            cluster = eks.describe_cluster(name=cluster_name)["cluster"]
            status = cluster.get("status", "")
            if status not in ("ACTIVE",):
                findings.append({
                    "category": "EKS",
                    "severity": SEVERITY_HIGH,
                    "title": f"EKS Cluster in {status} State",
                    "resource_id": cluster_name,
                    "details": f"Status: {status} | K8s version: {cluster.get('version')} | Region: {region}",
                    "action": "Investigate and restore the cluster to ACTIVE state or decommission it.",
                })
            # Check node groups
            ngs = eks.list_nodegroups(clusterName=cluster_name).get("nodegroups", [])
            for ng_name in ngs:
                ng = eks.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng_name)["nodegroup"]
                ng_status = ng.get("status", "")
                if ng_status not in ("ACTIVE",):
                    findings.append({
                        "category": "EKS",
                        "severity": SEVERITY_HIGH,
                        "title": f"EKS Node Group in {ng_status} State",
                        "resource_id": f"{cluster_name}/{ng_name}",
                        "details": f"Cluster: {cluster_name} | Status: {ng_status} | AMI: {ng.get('amiType')}",
                        "action": "Review node group health. Delete or recreate if degraded.",
                    })
                # Check for outdated k8s version (> 2 minor versions behind cluster)
                cluster_ver = cluster.get("version", "0.0")
                ng_ver = ng.get("version", "0.0")
                try:
                    c_minor = int(cluster_ver.split(".")[1])
                    n_minor = int(ng_ver.split(".")[1])
                    if c_minor - n_minor >= 2:
                        findings.append({
                            "category": "EKS",
                            "severity": SEVERITY_MEDIUM,
                            "title": "EKS Node Group Version Significantly Behind Cluster",
                            "resource_id": f"{cluster_name}/{ng_name}",
                            "details": f"Cluster: {cluster_ver} | Node group: {ng_ver} | Gap: {c_minor - n_minor} minor versions",
                            "action": "Update the node group Kubernetes version to match the cluster.",
                        })
                except (ValueError, IndexError):
                    pass
            # Check for old cluster version (< current - 2)
            # (AWS supports N-2 at most)
            try:
                minor = int(cluster.get("version", "1.99").split(".")[1])
                if minor < 27:  # Kubernetes 1.27 is the oldest actively supported
                    findings.append({
                        "category": "EKS",
                        "severity": SEVERITY_MEDIUM,
                        "title": "EKS Cluster Running Old Kubernetes Version",
                        "resource_id": cluster_name,
                        "details": f"Version: {cluster.get('version')} — AWS will end support soon.",
                        "action": "Upgrade the cluster to a supported Kubernetes version.",
                    })
            except (ValueError, IndexError):
                pass
        return findings
    return safe_check(_check, "EKS")


# ─── ECS ─────────────────────────────────────────────────────────────────────

def check_ecs_services(session, region):
    def _check():
        findings = []
        ecs = session.client("ecs", region_name=region)
        clusters = ecs.list_clusters().get("clusterArns", [])
        for cluster_arn in clusters:
            cluster_name = cluster_arn.split("/")[-1]
            # Services with 0 running tasks but desired > 0
            svc_arns = ecs.list_services(cluster=cluster_arn).get("serviceArns", [])
            if not svc_arns:
                continue
            services = ecs.describe_services(cluster=cluster_arn, services=svc_arns).get("services", [])
            for svc in services:
                desired = svc.get("desiredCount", 0)
                running = svc.get("runningCount", 0)
                pending = svc.get("pendingCount", 0)
                svc_name = svc.get("serviceName", "unknown")
                status = svc.get("status", "")

                if status != "ACTIVE":
                    findings.append({
                        "category": "ECS",
                        "severity": SEVERITY_MEDIUM,
                        "title": f"ECS Service in {status} State",
                        "resource_id": svc_name,
                        "details": f"Cluster: {cluster_name} | Status: {status} | Desired: {desired}",
                        "action": "Review and clean up inactive ECS services.",
                    })
                elif desired > 0 and running == 0 and pending == 0:
                    findings.append({
                        "category": "ECS",
                        "severity": SEVERITY_HIGH,
                        "title": "ECS Service with 0 Running Tasks (Desired > 0)",
                        "resource_id": svc_name,
                        "details": f"Cluster: {cluster_name} | Desired: {desired} | Running: 0 | Pending: 0",
                        "action": "Check ECS events and CloudWatch logs. Tasks may be failing to start.",
                    })
                elif desired == 0:
                    findings.append({
                        "category": "ECS",
                        "severity": SEVERITY_LOW,
                        "title": "ECS Service Scaled to Zero",
                        "resource_id": svc_name,
                        "details": f"Cluster: {cluster_name} | Desired: 0 — service is effectively stopped.",
                        "action": "Delete the service if no longer needed to avoid keeping unused definitions.",
                    })
        return findings
    return safe_check(_check, "ECS")


# ─── Kinesis Data Streams (KDS) ───────────────────────────────────────────────

def check_kinesis_data_streams(session, region):
    def _check():
        findings = []
        kin = session.client("kinesis", region_name=region)
        cw  = session.client("cloudwatch", region_name=region)
        streams = kin.list_streams().get("StreamNames", [])
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        for stream_name in streams:
            detail = kin.describe_stream_summary(StreamName=stream_name)
            sd = detail.get("StreamDescriptionSummary", {})
            encryption = sd.get("EncryptionType", "NONE")
            retention  = sd.get("RetentionPeriodHours", 24)
            shard_count = sd.get("OpenShardCount", 0)

            # Unencrypted stream
            if encryption == "NONE":
                findings.append({
                    "category": "KDS",
                    "severity": SEVERITY_HIGH,
                    "title": "Kinesis Data Stream Without Encryption",
                    "resource_id": stream_name,
                    "details": f"Encryption: {encryption} | Shards: {shard_count} | Retention: {retention}h",
                    "action": "Enable server-side encryption (SSE) using KMS for this stream.",
                })

            # Low retention (< 24h production risk)
            if retention < 24:
                findings.append({
                    "category": "KDS",
                    "severity": SEVERITY_MEDIUM,
                    "title": "Kinesis Data Stream with Low Retention Period",
                    "resource_id": stream_name,
                    "details": f"Retention: {retention} hours (< 24h). Data loss risk if consumers fall behind.",
                    "action": "Increase retention period to at least 24 hours (168h recommended for production).",
                })

            # Check GetRecords.IteratorAgeMilliseconds — high lag
            iterator_age = cw.get_metric_statistics(
                Namespace="AWS/Kinesis",
                MetricName="GetRecords.IteratorAgeMilliseconds",
                Dimensions=[{"Name": "StreamName", "Value": stream_name}],
                StartTime=start, EndTime=end,
                Period=604800, Statistics=["Maximum"],
            )
            for dp in iterator_age.get("Datapoints", []):
                age_hrs = dp["Maximum"] / (1000 * 3600)
                if age_hrs > 1:
                    findings.append({
                        "category": "KDS",
                        "severity": SEVERITY_MEDIUM,
                        "title": "Kinesis Stream Consumer Falling Behind",
                        "resource_id": stream_name,
                        "details": f"Max iterator age: {age_hrs:.1f} hours — consumers are not keeping up.",
                        "action": "Scale up consumers or increase shard count to reduce processing lag.",
                    })
                    break
        return findings
    return safe_check(_check, "KDS")


# ─── Kinesis Firehose (KFH) ───────────────────────────────────────────────────

def check_kinesis_firehose(session, region):
    def _check():
        findings = []
        fh  = session.client("firehose", region_name=region)
        cw  = session.client("cloudwatch", region_name=region)
        streams = fh.list_delivery_streams().get("DeliveryStreamNames", [])
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        for stream_name in streams:
            detail = fh.describe_delivery_stream(DeliveryStreamName=stream_name)
            sd = detail.get("DeliveryStreamDescription", {})
            status = sd.get("DeliveryStreamStatus", "")
            dest = sd.get("Destinations", [{}])[0]

            if status != "ACTIVE":
                findings.append({
                    "category": "KFH",
                    "severity": SEVERITY_HIGH,
                    "title": f"Firehose Delivery Stream in {status} State",
                    "resource_id": stream_name,
                    "details": f"Status: {status}",
                    "action": "Investigate and restore the Firehose stream. Data may be lost.",
                })

            # Check DeliveryToS3.DataFreshness (delivery lag)
            freshness = cw.get_metric_statistics(
                Namespace="AWS/Firehose",
                MetricName="DeliveryToS3.DataFreshness",
                Dimensions=[{"Name": "DeliveryStreamName", "Value": stream_name}],
                StartTime=start, EndTime=end,
                Period=604800, Statistics=["Maximum"],
            )
            for dp in freshness.get("Datapoints", []):
                lag_min = dp["Maximum"] / 60
                if lag_min > 60:  # > 1 hour lag
                    findings.append({
                        "category": "KFH",
                        "severity": SEVERITY_MEDIUM,
                        "title": "Firehose Stream with High Delivery Lag",
                        "resource_id": stream_name,
                        "details": f"Max data freshness: {lag_min:.0f} min — data delivered late to destination.",
                        "action": "Check destination (S3/Redshift) availability and Firehose buffer settings.",
                    })
                    break

            # Check for delivery failures
            failures = cw.get_metric_statistics(
                Namespace="AWS/Firehose",
                MetricName="DeliveryToS3.Success",
                Dimensions=[{"Name": "DeliveryStreamName", "Value": stream_name}],
                StartTime=start, EndTime=end,
                Period=604800, Statistics=["Average"],
            )
            for dp in failures.get("Datapoints", []):
                success_rate = dp["Average"] * 100
                if success_rate < 95:
                    findings.append({
                        "category": "KFH",
                        "severity": SEVERITY_HIGH,
                        "title": "Firehose Stream with Low Delivery Success Rate",
                        "resource_id": stream_name,
                        "details": f"Delivery success rate: {success_rate:.1f}% (last 7 days)",
                        "action": "Check destination permissions, S3 bucket policies, and Firehose error logs.",
                    })
                    break
        return findings
    return safe_check(_check, "KFH")


# ─── Master runner ───────────────────────────────────────────────────────────

def run_all_checks(session: boto3.Session, region: str) -> list:
    """Run all housekeeping checks and return a flat list of findings."""
    findings = []

    check_fns = [
        # EC2
        lambda: check_stopped_ec2(session, region),
        lambda: check_unattached_ebs(session, region),
        lambda: check_unused_elastic_ips(session, region),
        # IAM (global)
        lambda: check_iam_mfa(session, region),
        lambda: check_old_access_keys(session, region),
        lambda: check_inactive_users(session, region),
        # S3 (global)
        lambda: check_s3_public_access(session, region),
        lambda: check_s3_versioning(session, region),
        # Security Groups
        lambda: check_open_security_groups(session, region),
        lambda: check_unused_security_groups(session, region),
        # RDS
        lambda: check_stopped_rds(session, region),
        lambda: check_public_rds(session, region),
        # ELB
        lambda: check_idle_load_balancers(session, region),
        # Lambda
        lambda: check_lambda_errors(session, region),
        # CloudWatch
        lambda: check_cloudwatch_alarms(session, region),
        # EKS
        lambda: check_eks_node_groups(session, region),
        # ECS
        lambda: check_ecs_services(session, region),
        # Kinesis Data Streams
        lambda: check_kinesis_data_streams(session, region),
        # Kinesis Firehose
        lambda: check_kinesis_firehose(session, region),
        # VPC
        lambda: check_vpc_flow_logs(session, region),
        lambda: check_default_vpc(session, region),
        lambda: check_unused_nat_gateways(session, region),
    ]

    for fn in check_fns:
        results = fn()
        findings.extend(results)

    return findings

