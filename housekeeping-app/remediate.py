"""
AWS Housekeeping — Remediation Engine
Each remediate_* function returns a list of step dicts:
  { step, status, message, timestamp }
status values: "running" | "success" | "error" | "skipped"
"""

import time
from datetime import datetime, timezone
import botocore.exceptions


def _step(step_num, status, message):
    return {
        "step": step_num,
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── EC2 ─────────────────────────────────────────────────────────────────────

def remediate_stopped_ec2(session, region, resource_id):
    """Snapshot root EBS volume then terminate the stopped EC2 instance."""
    steps = []
    ec2 = session.client("ec2", region_name=region)

    try:
        steps.append(_step(1, "running", f"Fetching details for instance {resource_id}…"))
        resp = ec2.describe_instances(InstanceIds=[resource_id])
        reservations = resp.get("Reservations", [])
        if not reservations:
            steps[-1] = _step(1, "error", f"Instance {resource_id} not found.")
            return steps
        instance = reservations[0]["Instances"][0]
        state = instance["State"]["Name"]
        steps[-1] = _step(1, "success", f"Instance found. State: {state} | Type: {instance.get('InstanceType')}")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Failed to describe instance: {e}")
        return steps

    # Snapshot root volume
    root_device = instance.get("RootDeviceName", "/dev/xvda")
    root_vol_id = None
    for mapping in instance.get("BlockDeviceMappings", []):
        if mapping.get("DeviceName") == root_device:
            root_vol_id = mapping.get("Ebs", {}).get("VolumeId")
            break

    if root_vol_id:
        try:
            steps.append(_step(2, "running", f"Creating snapshot of root volume {root_vol_id} before termination…"))
            snap = ec2.create_snapshot(
                VolumeId=root_vol_id,
                Description=f"Pre-termination snapshot of {resource_id} by AWS Housekeeping",
                TagSpecifications=[{
                    "ResourceType": "snapshot",
                    "Tags": [
                        {"Key": "Name", "Value": f"hk-pre-terminate-{resource_id}"},
                        {"Key": "CreatedBy", "Value": "aws-housekeeping"},
                    ]
                }]
            )
            steps[-1] = _step(2, "success", f"Snapshot {snap['SnapshotId']} created (status: pending, will complete in background).")
        except Exception as e:
            steps.append(_step(2, "error", f"Could not create snapshot (continuing anyway): {e}"))
    else:
        steps.append(_step(2, "skipped", "No root EBS volume found — skipping snapshot step."))

    # Terminate
    try:
        steps.append(_step(3, "running", f"Terminating instance {resource_id}…"))
        ec2.terminate_instances(InstanceIds=[resource_id])
        steps[-1] = _step(3, "success", f"✅ Instance {resource_id} termination initiated successfully.")
    except Exception as e:
        steps[-1] = _step(3, "error", f"Termination failed: {e}")

    return steps


def remediate_unattached_ebs(session, region, resource_id):
    """Snapshot then delete an unattached EBS volume."""
    steps = []
    ec2 = session.client("ec2", region_name=region)

    try:
        steps.append(_step(1, "running", f"Verifying volume {resource_id} is unattached…"))
        resp = ec2.describe_volumes(VolumeIds=[resource_id])
        vol = resp["Volumes"][0]
        if vol["State"] != "available":
            steps[-1] = _step(1, "error", f"Volume state is '{vol['State']}' — not safe to delete.")
            return steps
        steps[-1] = _step(1, "success", f"Volume confirmed unattached. Size: {vol['Size']} GiB | Type: {vol['VolumeType']}")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Failed to describe volume: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Creating safety snapshot of {resource_id}…"))
        snap = ec2.create_snapshot(
            VolumeId=resource_id,
            Description=f"Pre-delete snapshot by AWS Housekeeping",
            TagSpecifications=[{
                "ResourceType": "snapshot",
                "Tags": [
                    {"Key": "Name", "Value": f"hk-pre-delete-{resource_id}"},
                    {"Key": "CreatedBy", "Value": "aws-housekeeping"},
                ]
            }]
        )
        steps[-1] = _step(2, "success", f"Snapshot {snap['SnapshotId']} initiated.")
    except Exception as e:
        steps.append(_step(2, "error", f"Snapshot failed (aborting for safety): {e}"))
        return steps

    try:
        steps.append(_step(3, "running", f"Deleting volume {resource_id}…"))
        ec2.delete_volume(VolumeId=resource_id)
        steps[-1] = _step(3, "success", f"✅ Volume {resource_id} deleted. Snapshot preserved for recovery.")
    except Exception as e:
        steps[-1] = _step(3, "error", f"Delete failed: {e}")

    return steps


def remediate_unused_elastic_ip(session, region, resource_id):
    """Release an unassociated Elastic IP."""
    steps = []
    ec2 = session.client("ec2", region_name=region)

    try:
        steps.append(_step(1, "running", f"Looking up Elastic IP allocation {resource_id}…"))
        resp = ec2.describe_addresses(AllocationIds=[resource_id])
        addr = resp["Addresses"][0]
        if addr.get("AssociationId"):
            steps[-1] = _step(1, "error", "IP is currently associated with a resource — not safe to release.")
            return steps
        steps[-1] = _step(1, "success", f"Confirmed unassociated. Public IP: {addr.get('PublicIp')}")
    except Exception as e:
        # May be a PublicIp, not AllocationId
        try:
            resp = ec2.describe_addresses(PublicIps=[resource_id])
            addr = resp["Addresses"][0]
            resource_id = addr.get("AllocationId", resource_id)
            steps.append(_step(1, "success", f"Found by PublicIp. AllocationId: {resource_id}"))
        except Exception as e2:
            steps[-1] = _step(1, "error", f"Cannot find address: {e2}")
            return steps

    try:
        steps.append(_step(2, "running", f"Releasing Elastic IP {resource_id}…"))
        ec2.release_address(AllocationId=resource_id)
        steps[-1] = _step(2, "success", f"✅ Elastic IP released. Idle charges will stop immediately.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Release failed: {e}")

    return steps


# ─── IAM ─────────────────────────────────────────────────────────────────────

def remediate_iam_no_mfa(session, region, resource_id):
    """Disable console login for IAM user without MFA."""
    steps = []
    iam = session.client("iam")

    try:
        steps.append(_step(1, "running", f"Checking console access for user {resource_id}…"))
        iam.get_login_profile(UserName=resource_id)
        steps[-1] = _step(1, "success", "User has console password login enabled.")
    except iam.exceptions.NoSuchEntityException:
        steps[-1] = _step(1, "skipped", "User has no console password — console access already disabled.")
        return steps
    except Exception as e:
        steps[-1] = _step(1, "error", f"Error: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Disabling console login profile for {resource_id}…"))
        iam.delete_login_profile(UserName=resource_id)
        steps[-1] = _step(2, "success", f"✅ Console access disabled for {resource_id}. User must re-enable MFA before regaining access.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Failed: {e}")

    return steps


def remediate_old_access_key(session, region, resource_id):
    """Deactivate an old IAM access key."""
    steps = []
    iam = session.client("iam")

    # resource_id is the AccessKeyId — find the user
    try:
        steps.append(_step(1, "running", f"Finding user for access key {resource_id}…"))
        paginator = iam.get_paginator("list_users")
        target_user = None
        for page in paginator.paginate():
            for user in page["Users"]:
                keys = iam.list_access_keys(UserName=user["UserName"])["AccessKeyMetadata"]
                for k in keys:
                    if k["AccessKeyId"] == resource_id:
                        target_user = user["UserName"]
                        break
                if target_user:
                    break
        if not target_user:
            steps[-1] = _step(1, "error", f"Access key {resource_id} not found.")
            return steps
        steps[-1] = _step(1, "success", f"Key belongs to user: {target_user}")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Lookup failed: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Deactivating access key {resource_id} for {target_user}…"))
        iam.update_access_key(UserName=target_user, AccessKeyId=resource_id, Status="Inactive")
        steps[-1] = _step(2, "success", f"✅ Access key {resource_id} deactivated. The key is inactive but not deleted — can be restored if needed.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Deactivation failed: {e}")

    return steps


def remediate_inactive_user(session, region, resource_id):
    """Disable console and deactivate all access keys for inactive IAM user."""
    steps = []
    iam = session.client("iam")

    # Disable console
    try:
        steps.append(_step(1, "running", f"Disabling console login for {resource_id}…"))
        iam.delete_login_profile(UserName=resource_id)
        steps[-1] = _step(1, "success", "Console login disabled.")
    except iam.exceptions.NoSuchEntityException:
        steps[-1] = _step(1, "skipped", "No console login profile found — already disabled.")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Error: {e}")

    # Deactivate access keys
    try:
        steps.append(_step(2, "running", f"Deactivating all active access keys for {resource_id}…"))
        keys = iam.list_access_keys(UserName=resource_id)["AccessKeyMetadata"]
        active_keys = [k for k in keys if k["Status"] == "Active"]
        if not active_keys:
            steps[-1] = _step(2, "skipped", "No active access keys found.")
        else:
            for k in active_keys:
                iam.update_access_key(UserName=resource_id, AccessKeyId=k["AccessKeyId"], Status="Inactive")
            steps[-1] = _step(2, "success", f"✅ Deactivated {len(active_keys)} access key(s) for {resource_id}.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Failed to deactivate keys: {e}")

    return steps


# ─── S3 ──────────────────────────────────────────────────────────────────────

def remediate_s3_public_access(session, region, resource_id):
    """Enable all 4 Block Public Access settings on an S3 bucket."""
    steps = []
    s3 = session.client("s3")

    try:
        steps.append(_step(1, "running", f"Reading current public access block config for {resource_id}…"))
        try:
            existing = s3.get_public_access_block(Bucket=resource_id)
            cfg = existing["PublicAccessBlockConfiguration"]
            steps[-1] = _step(1, "success",
                f"Current: BlockPublicAcls={cfg.get('BlockPublicAcls')} | "
                f"BlockPublicPolicy={cfg.get('BlockPublicPolicy')} | "
                f"RestrictPublicBuckets={cfg.get('RestrictPublicBuckets')}")
        except s3.exceptions.NoSuchPublicAccessBlockConfiguration:
            steps[-1] = _step(1, "success", "No config exists — will create fresh block configuration.")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Error: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Enabling all Block Public Access settings on {resource_id}…"))
        s3.put_public_access_block(
            Bucket=resource_id,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        )
        steps[-1] = _step(2, "success", f"✅ All 4 Block Public Access settings enabled on bucket '{resource_id}'.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Failed: {e}")

    return steps


def remediate_s3_versioning(session, region, resource_id):
    """Enable versioning on an S3 bucket."""
    steps = []
    s3 = session.client("s3")

    try:
        steps.append(_step(1, "running", f"Checking current versioning status for {resource_id}…"))
        v = s3.get_bucket_versioning(Bucket=resource_id)
        current = v.get("Status", "Disabled")
        steps[-1] = _step(1, "success", f"Current versioning status: {current}")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Error: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Enabling versioning on bucket {resource_id}…"))
        s3.put_bucket_versioning(
            Bucket=resource_id,
            VersioningConfiguration={"Status": "Enabled"}
        )
        steps[-1] = _step(2, "success", f"✅ Versioning enabled on '{resource_id}'. Object recovery is now available.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Failed: {e}")

    return steps


# ─── Security Groups ─────────────────────────────────────────────────────────

def remediate_open_security_group(session, region, resource_id, finding_title):
    """Revoke the open-world inbound rule for the detected risky port."""
    steps = []
    ec2 = session.client("ec2", region_name=region)

    # Parse port from finding title e.g. "Security Group Open to World on SSH (port 22)"
    port = None
    import re
    m = re.search(r"port (\d+)", finding_title or "")
    if m:
        port = int(m.group(1))

    try:
        steps.append(_step(1, "running", f"Fetching inbound rules for {resource_id}…"))
        resp = ec2.describe_security_groups(GroupIds=[resource_id])
        sg = resp["SecurityGroups"][0]
        steps[-1] = _step(1, "success", f"SG: {sg.get('GroupName')} | VPC: {sg.get('VpcId')}")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Cannot describe security group: {e}")
        return steps

    open_cidrs = {"0.0.0.0/0", "::/0"}
    rules_to_revoke_v4 = []
    rules_to_revoke_v6 = []

    for perm in sg.get("IpPermissions", []):
        from_p = perm.get("FromPort", 0)
        to_p = perm.get("ToPort", 65535)
        if port is not None and not (from_p <= port <= to_p):
            continue
        for rng in perm.get("IpRanges", []):
            if rng.get("CidrIp") in open_cidrs:
                rules_to_revoke_v4.append({
                    "IpProtocol": perm["IpProtocol"],
                    "FromPort": from_p,
                    "ToPort": to_p,
                    "IpRanges": [{"CidrIp": rng["CidrIp"]}],
                })
        for rng in perm.get("Ipv6Ranges", []):
            if rng.get("CidrIpv6") in open_cidrs:
                rules_to_revoke_v6.append({
                    "IpProtocol": perm["IpProtocol"],
                    "FromPort": from_p,
                    "ToPort": to_p,
                    "Ipv6Ranges": [{"CidrIpv6": rng["CidrIpv6"]}],
                })

    if not rules_to_revoke_v4 and not rules_to_revoke_v6:
        steps.append(_step(2, "skipped", "No open-world inbound rules found for the detected port — may already be remediated."))
        return steps

    try:
        steps.append(_step(2, "running", f"Revoking {len(rules_to_revoke_v4 + rules_to_revoke_v6)} open-world inbound rule(s)…"))
        if rules_to_revoke_v4:
            ec2.revoke_security_group_ingress(GroupId=resource_id, IpPermissions=rules_to_revoke_v4)
        if rules_to_revoke_v6:
            ec2.revoke_security_group_ingress(GroupId=resource_id, IpPermissions=rules_to_revoke_v6)
        steps[-1] = _step(2, "success",
            f"✅ Revoked {len(rules_to_revoke_v4 + rules_to_revoke_v6)} open inbound rule(s) from {resource_id}. "
            "Access is now restricted — update with specific CIDR if needed.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Revoke failed: {e}")

    return steps


def remediate_unused_security_group(session, region, resource_id):
    """Delete an unused security group."""
    steps = []
    ec2 = session.client("ec2", region_name=region)

    try:
        steps.append(_step(1, "running", f"Verifying {resource_id} is unused…"))
        enis = ec2.describe_network_interfaces(
            Filters=[{"Name": "group-id", "Values": [resource_id]}]
        ).get("NetworkInterfaces", [])
        if enis:
            steps[-1] = _step(1, "error", f"Security group is attached to {len(enis)} ENI(s) — cannot delete.")
            return steps
        steps[-1] = _step(1, "success", "Confirmed: no ENIs attached.")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Check failed: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Deleting security group {resource_id}…"))
        ec2.delete_security_group(GroupId=resource_id)
        steps[-1] = _step(2, "success", f"✅ Security group {resource_id} deleted successfully.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Delete failed: {e}")

    return steps


# ─── RDS ─────────────────────────────────────────────────────────────────────

def remediate_public_rds(session, region, resource_id):
    """Modify RDS instance to not be publicly accessible."""
    steps = []
    rds = session.client("rds", region_name=region)

    try:
        steps.append(_step(1, "running", f"Verifying RDS instance {resource_id}…"))
        resp = rds.describe_db_instances(DBInstanceIdentifier=resource_id)
        db = resp["DBInstances"][0]
        steps[-1] = _step(1, "success",
            f"Engine: {db['Engine']} {db['EngineVersion']} | Class: {db['DBInstanceClass']} | "
            f"PubliclyAccessible: {db['PubliclyAccessible']}")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Cannot describe RDS instance: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Modifying {resource_id} — setting PubliclyAccessible=False…"))
        rds.modify_db_instance(
            DBInstanceIdentifier=resource_id,
            PubliclyAccessible=False,
            ApplyImmediately=True
        )
        steps[-1] = _step(2, "success",
            f"✅ Modification submitted. RDS instance {resource_id} will become private. "
            "Allow 1-2 minutes for the change to apply.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Modification failed: {e}")

    return steps


# ─── CloudWatch ──────────────────────────────────────────────────────────────

def remediate_cloudwatch_alarm(session, region, resource_id):
    """Delete a CloudWatch alarm stuck in INSUFFICIENT_DATA."""
    steps = []
    cw = session.client("cloudwatch", region_name=region)

    try:
        steps.append(_step(1, "running", f"Verifying alarm '{resource_id}' state…"))
        resp = cw.describe_alarms(AlarmNames=[resource_id])
        alarms = resp.get("MetricAlarms", [])
        if not alarms:
            steps[-1] = _step(1, "error", "Alarm not found.")
            return steps
        alarm = alarms[0]
        steps[-1] = _step(1, "success",
            f"Alarm state: {alarm['StateValue']} | Metric: {alarm.get('MetricName')} | "
            f"Namespace: {alarm.get('Namespace')}")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Error: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Deleting alarm '{resource_id}'…"))
        cw.delete_alarms(AlarmNames=[resource_id])
        steps[-1] = _step(2, "success", f"✅ Alarm '{resource_id}' deleted.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Delete failed: {e}")

    return steps


# ─── Kinesis ─────────────────────────────────────────────────────────────────

def remediate_kinesis_no_encryption(session, region, resource_id):
    """Enable KMS SSE encryption on a Kinesis Data Stream."""
    steps = []
    kin = session.client("kinesis", region_name=region)

    try:
        steps.append(_step(1, "running", f"Checking encryption status for stream '{resource_id}'…"))
        detail = kin.describe_stream_summary(StreamName=resource_id)
        enc = detail["StreamDescriptionSummary"].get("EncryptionType", "NONE")
        steps[-1] = _step(1, "success", f"Current encryption: {enc}")
        if enc != "NONE":
            steps.append(_step(2, "skipped", "Stream is already encrypted — no action needed."))
            return steps
    except Exception as e:
        steps[-1] = _step(1, "error", f"Error: {e}")
        return steps

    try:
        steps.append(_step(2, "running", f"Enabling SSE encryption with AWS-managed KMS key on '{resource_id}'…"))
        kin.start_stream_encryption(
            StreamName=resource_id,
            EncryptionType="KMS",
            KeyId="alias/aws/kinesis"
        )
        steps[-1] = _step(2, "success",
            f"✅ KMS encryption enabled for stream '{resource_id}' using aws/kinesis managed key. "
            "Encryption applies to new records immediately.")
    except Exception as e:
        steps[-1] = _step(2, "error", f"Encryption failed: {e}")

    return steps


def remediate_vpc_flow_logs(session, region, resource_id):
    """Create a CloudWatch Log Group and enable VPC Flow Logs for the given VPC."""
    steps = []
    ec2 = session.client("ec2", region_name=region)
    logs = session.client("logs", region_name=region)
    iam = session.client("iam")
    import json
    
    log_group_name = f"vpc-flow-logs-{resource_id}"
    role_name = "VPCFlowLogsRole"
    
    # 1. Create Log Group
    try:
        steps.append(_step(1, "running", f"Creating CloudWatch Log Group '{log_group_name}'…"))
        logs.create_log_group(logGroupName=log_group_name)
        steps[-1] = _step(1, "success", f"Log group created.")
    except logs.exceptions.ResourceAlreadyExistsException:
        steps[-1] = _step(1, "success", f"Log group '{log_group_name}' already exists.")
    except Exception as e:
        steps[-1] = _step(1, "error", f"Failed to create log group: {e}")
        return steps

    # 2. Ensure IAM Role exists
    try:
        steps.append(_step(2, "running", f"Ensuring IAM role '{role_name}' exists for Flow Logs…"))
        try:
            role = iam.get_role(RoleName=role_name)
            role_arn = role["Role"]["Arn"]
            steps[-1] = _step(2, "success", f"Role exists: {role_arn}")
        except iam.exceptions.NoSuchEntityException:
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "vpc-flow-logs.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            role = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Role for VPC Flow Logs to write to CloudWatch"
            )
            role_arn = role["Role"]["Arn"]
            policy_doc = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                        "logs:DescribeLogGroups", "logs:DescribeLogStreams"
                    ],
                    "Resource": "*"
                }]
            }
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName="VPCFlowLogsPolicy",
                PolicyDocument=json.dumps(policy_doc)
            )
            steps[-1] = _step(2, "success", f"Created role {role_arn} and attached permissions.")
            time.sleep(5)
    except Exception as e:
        steps[-1] = _step(2, "error", f"IAM Role setup failed: {e}")
        return steps

    # 3. Enable Flow Logs
    try:
        steps.append(_step(3, "running", f"Enabling Flow Logs for VPC {resource_id}…"))
        ec2.create_flow_logs(
            ResourceIds=[resource_id],
            ResourceType="VPC",
            TrafficType="ALL",
            LogGroupName=log_group_name,
            DeliverLogsPermissionArn=role_arn
        )
        steps[-1] = _step(3, "success", f"✅ VPC Flow Logs enabled successfully. Traffic is now being logged to CloudWatch.")
    except Exception as e:
        steps[-1] = _step(3, "error", f"Failed to enable flow logs: {e}")

    return steps


# ─── Dispatcher ─────────────────────────────────────────────────────────────

def dispatch_remediation(session, region, finding):
    """
    Route a finding to the correct remediation function.
    Returns list of step dicts.
    """
    category = finding.get("category", "")
    title = finding.get("title", "")
    resource_id = finding.get("resource_id", "")

    if category == "EC2":
        if "Stopped EC2" in title:
            return remediate_stopped_ec2(session, region, resource_id)
        elif "Unattached EBS" in title:
            return remediate_unattached_ebs(session, region, resource_id)
        elif "Unused Elastic IP" in title:
            return remediate_unused_elastic_ip(session, region, resource_id)

    elif category == "IAM":
        if "Without MFA" in title:
            return remediate_iam_no_mfa(session, region, resource_id)
        elif "Access Key" in title:
            return remediate_old_access_key(session, region, resource_id)
        elif "Inactive IAM User" in title:
            return remediate_inactive_user(session, region, resource_id)

    elif category == "S3":
        if "Public Access" in title:
            return remediate_s3_public_access(session, region, resource_id)
        elif "Versioning" in title:
            return remediate_s3_versioning(session, region, resource_id)

    elif category == "Security Groups":
        if "Open to World" in title:
            return remediate_open_security_group(session, region, resource_id, title)
        elif "Unused Security Group" in title:
            return remediate_unused_security_group(session, region, resource_id)

    elif category == "RDS":
        if "Publicly Accessible" in title:
            return remediate_public_rds(session, region, resource_id)

    elif category == "CloudWatch":
        if "INSUFFICIENT_DATA" in title:
            return remediate_cloudwatch_alarm(session, region, resource_id)

    elif category == "KDS":
        if "Without Encryption" in title:
            return remediate_kinesis_no_encryption(session, region, resource_id)

    elif category == "VPC":
        if "Flow Logs" in title:
            return remediate_vpc_flow_logs(session, region, resource_id)

    return [{
        "step": 1,
        "status": "skipped",
        "message": f"No automated remediation available for '{title}'. Please follow the recommended action manually.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }]
