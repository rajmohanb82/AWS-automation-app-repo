"""
AWS Cost Optimizer — Resource Scanner
Collects resource inventory + CloudWatch utilization metrics for all major services.
Returns structured data for the AI advisor and frontend dashboard.
"""

import json
from datetime import datetime, timezone, timedelta

import boto3
import botocore.exceptions


# ─── Dynamic Live Pricing Integration ─────────────────────────────────────────

HOURS_PER_MONTH = 730

REGION_MAP = {
    "us-east-1": "US East (N. Virginia)", "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)", "us-west-2": "US West (Oregon)",
    "ap-south-1": "Asia Pacific (Mumbai)", "ap-south-2": "Asia Pacific (Hyderabad)",
    "ap-southeast-1": "Asia Pacific (Singapore)", "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)", "eu-west-1": "Europe (Ireland)",
    "eu-west-2": "Europe (London)", "eu-central-1": "Europe (Frankfurt)",
    "ca-central-1": "Canada (Central)"
}

SESSION_PRICE_CACHE = {}

def get_live_ec2_price(session, region, instance_type):
    cache_key = f"ec2_{region}_{instance_type}"
    if cache_key in SESSION_PRICE_CACHE:
        return SESSION_PRICE_CACHE[cache_key]
    
    try:
        pricing = session.client('pricing', region_name='us-east-1')
        location = REGION_MAP.get(region, "US East (N. Virginia)")
        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location}
            ],
            MaxResults=1
        )
        if response.get('PriceList'):
            price_data = json.loads(response['PriceList'][0])
            on_demand = price_data['terms']['OnDemand']
            term_val = list(on_demand.values())[0]
            price_dim = list(term_val['priceDimensions'].values())[0]
            price = float(price_dim['pricePerUnit']['USD'])
            SESSION_PRICE_CACHE[cache_key] = price
            return price
    except Exception:
        pass
    
    price = 0.10
    SESSION_PRICE_CACHE[cache_key] = price
    return price

def get_live_rds_price(session, region, db_class):
    cache_key = f"rds_{region}_{db_class}"
    if cache_key in SESSION_PRICE_CACHE:
        return SESSION_PRICE_CACHE[cache_key]
    
    try:
        pricing = session.client('pricing', region_name='us-east-1')
        location = REGION_MAP.get(region, "US East (N. Virginia)")
        response = pricing.get_products(
            ServiceCode='AmazonRDS',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': db_class},
                {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'},
                {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'Single-AZ'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location}
            ],
            MaxResults=1
        )
        if response.get('PriceList'):
            price_data = json.loads(response['PriceList'][0])
            on_demand = price_data['terms']['OnDemand']
            term_val = list(on_demand.values())[0]
            price_dim = list(term_val['priceDimensions'].values())[0]
            price = float(price_dim['pricePerUnit']['USD'])
            SESSION_PRICE_CACHE[cache_key] = price
            return price
    except Exception:
        pass
        
    price = 0.20
    SESSION_PRICE_CACHE[cache_key] = price
    return price

def get_live_ebs_price(session, region, volume_type):
    cache_key = f"ebs_{region}_{volume_type}"
    if cache_key in SESSION_PRICE_CACHE:
        return SESSION_PRICE_CACHE[cache_key]
        
    try:
        pricing = session.client('pricing', region_name='us-east-1')
        location = REGION_MAP.get(region, "US East (N. Virginia)")
        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'},
                {'Type': 'TERM_MATCH', 'Field': 'volumeApiName', 'Value': volume_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location}
            ],
            MaxResults=1
        )
        if response.get('PriceList'):
            price_data = json.loads(response['PriceList'][0])
            on_demand = price_data['terms']['OnDemand']
            term_val = list(on_demand.values())[0]
            price_dim = list(term_val['priceDimensions'].values())[0]
            price = float(price_dim['pricePerUnit']['USD'])
            SESSION_PRICE_CACHE[cache_key] = price
            return price
    except Exception:
        pass
        
    price = 0.10
    SESSION_PRICE_CACHE[cache_key] = price
    return price


def _cw_avg(cw, namespace, metric, dims, days=14):
    """Fetch average of a CW metric over the last N days. Returns float or None."""
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        resp = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric,
            Dimensions=dims,
            StartTime=start, EndTime=end,
            Period=days * 86400,
            Statistics=["Average"],
        )
        dps = resp.get("Datapoints", [])
        if not dps:
            return None
        return round(sum(d["Average"] for d in dps) / len(dps), 2)
    except Exception:
        return None


def _cw_sum(cw, namespace, metric, dims, days=14):
    """Fetch sum of a CW metric over the last N days."""
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        resp = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric,
            Dimensions=dims,
            StartTime=start, EndTime=end,
            Period=days * 86400,
            Statistics=["Sum"],
        )
        dps = resp.get("Datapoints", [])
        if not dps:
            return None
        return round(sum(d["Sum"] for d in dps), 2)
    except Exception:
        return None


def _safe(fn):
    try:
        return fn()
    except Exception:
        return []


# ─── EC2 ─────────────────────────────────────────────────────────────────────

def scan_ec2(session, region):
    ec2 = session.client("ec2", region_name=region)
    cw  = session.client("cloudwatch", region_name=region)
    resources = []

    try:
        resp = ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["running", "stopped"]}]
        )
    except Exception:
        return resources

    for reservation in resp.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            iid  = inst["InstanceId"]
            itype = inst.get("InstanceType", "unknown")
            state = inst["State"]["Name"]
            name  = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), iid)

            hourly_price = get_live_ec2_price(session, region, itype)
            monthly_cost = round(hourly_price * HOURS_PER_MONTH, 2) if state == "running" else 0.0

            cpu_avg = None
            if state == "running":
                cpu_avg = _cw_avg(cw, "AWS/EC2", "CPUUtilization",
                                  [{"Name": "InstanceId", "Value": iid}])

            # Downsize suggestion
            suggestion = None
            saving = 0.0
            if cpu_avg is not None and cpu_avg < 5 and state == "running":
                # Find smaller instance type
                parts = itype.split(".")
                if len(parts) == 2:
                    family, size = parts
                    downsizes = {"2xlarge": "xlarge", "xlarge": "large", "large": "medium",
                                 "medium": "small", "small": "micro"}
                    next_size = downsizes.get(size)
                    if next_size:
                        new_type = f"{family}.{next_size}"
                        new_price = get_live_ec2_price(session, region, new_type)
                        saving = round((hourly_price - new_price) * HOURS_PER_MONTH, 2)
                        suggestion = f"Downsize to {new_type} (CPU avg {cpu_avg}%)"
            elif state == "stopped":
                suggestion = "Terminate stopped instance"
                # EBS costs still apply for stopped

            resources.append({
                "service": "EC2",
                "resource_id": iid,
                "name": name,
                "type": itype,
                "state": state,
                "monthly_cost": monthly_cost,
                "cpu_avg_pct": cpu_avg,
                "suggestion": suggestion,
                "potential_saving": saving,
                "region": region,
            })

    return resources


# ─── EBS ─────────────────────────────────────────────────────────────────────

def scan_ebs(session, region):
    ec2 = session.client("ec2", region_name=region)
    cw  = session.client("cloudwatch", region_name=region)
    resources = []

    try:
        resp = ec2.describe_volumes()
    except Exception:
        return resources

    for vol in resp.get("Volumes", []):
        vid   = vol["VolumeId"]
        size  = vol.get("Size", 0)
        vtype = vol.get("VolumeType", "gp2")
        state = vol.get("State", "unknown")
        name  = next((t["Value"] for t in vol.get("Tags", []) if t["Key"] == "Name"), vid)

        price_per_gb = get_live_ebs_price(session, region, vtype)
        monthly_cost = round(size * price_per_gb, 2)

        iops_avg = _cw_avg(cw, "AWS/EBS", "VolumeReadOps",
                           [{"Name": "VolumeId", "Value": vid}])

        suggestion = None
        saving = 0.0
        if state == "available":
            suggestion = "Delete unattached volume (snapshot first)"
            saving = monthly_cost
        elif vtype == "gp2" and size >= 100:
            # gp3 is always cheaper than gp2
            gp2_price = get_live_ebs_price(session, region, "gp2")
            gp3_price = get_live_ebs_price(session, region, "gp3")
            saving = round(size * (gp2_price - gp3_price), 2)
            suggestion = f"Migrate from gp2 to gp3 (save ${saving}/mo)"

        resources.append({
            "service": "EBS",
            "resource_id": vid,
            "name": name,
            "type": vtype,
            "state": state,
            "size_gb": size,
            "monthly_cost": monthly_cost,
            "iops_avg": iops_avg,
            "suggestion": suggestion,
            "potential_saving": saving,
            "region": region,
        })

    return resources


# ─── RDS ─────────────────────────────────────────────────────────────────────

def scan_rds(session, region):
    rds = session.client("rds", region_name=region)
    cw  = session.client("cloudwatch", region_name=region)
    resources = []

    try:
        instances = rds.describe_db_instances().get("DBInstances", [])
    except Exception:
        return resources

    for db in instances:
        dbid     = db["DBInstanceIdentifier"]
        dbclass  = db["DBInstanceClass"]
        state    = db["DBInstanceStatus"]
        engine   = db["Engine"]
        storage  = db.get("AllocatedStorage", 0)

        hourly = get_live_rds_price(session, region, dbclass)
        storage_cost = round(storage * 0.115, 2)  # gp2 RDS storage
        compute_cost = round(hourly * HOURS_PER_MONTH, 2) if state == "available" else 0
        monthly_cost = compute_cost + storage_cost

        cpu_avg = _cw_avg(cw, "AWS/RDS", "CPUUtilization",
                          [{"Name": "DBInstanceIdentifier", "Value": dbid}])
        conn_avg = _cw_avg(cw, "AWS/RDS", "DatabaseConnections",
                           [{"Name": "DBInstanceIdentifier", "Value": dbid}])

        suggestion = None
        saving = 0.0
        if state == "stopped":
            suggestion = "Delete stopped RDS instance"
            saving = storage_cost
        elif cpu_avg is not None and cpu_avg < 5 and conn_avg is not None and conn_avg < 2:
            suggestion = f"Downsize DB class (CPU avg {cpu_avg}%, conns avg {conn_avg})"
            saving = round(compute_cost * 0.45, 2)

        resources.append({
            "service": "RDS",
            "resource_id": dbid,
            "name": dbid,
            "type": dbclass,
            "state": state,
            "engine": engine,
            "monthly_cost": monthly_cost,
            "cpu_avg_pct": cpu_avg,
            "conn_avg": conn_avg,
            "suggestion": suggestion,
            "potential_saving": saving,
            "region": region,
        })

    return resources


# ─── Elastic IPs ─────────────────────────────────────────────────────────────

def scan_elastic_ips(session, region):
    ec2 = session.client("ec2", region_name=region)
    resources = []

    try:
        addrs = ec2.describe_addresses().get("Addresses", [])
    except Exception:
        return resources

    for addr in addrs:
        alloc_id = addr.get("AllocationId", addr.get("PublicIp", "N/A"))
        assoc    = addr.get("AssociationId")
        ip       = addr.get("PublicIp", "N/A")

        monthly_cost = 0.0 if assoc else 3.65  # $0.005/hr unassociated

        resources.append({
            "service": "Elastic IP",
            "resource_id": alloc_id,
            "name": ip,
            "type": "EIP",
            "state": "associated" if assoc else "unassociated",
            "monthly_cost": monthly_cost,
            "suggestion": "Release unused Elastic IP" if not assoc else None,
            "potential_saving": monthly_cost if not assoc else 0.0,
            "region": region,
        })

    return resources


# ─── ELB ─────────────────────────────────────────────────────────────────────

def scan_elb(session, region):
    elbv2 = session.client("elbv2", region_name=region)
    cw    = session.client("cloudwatch", region_name=region)
    resources = []

    try:
        lbs = elbv2.describe_load_balancers().get("LoadBalancers", [])
    except Exception:
        return resources

    for lb in lbs:
        lb_name = lb["LoadBalancerName"]
        lb_arn  = lb["LoadBalancerArn"]
        lb_type = lb.get("Type", "application")

        # ALB: ~$16.2/mo base + LCU costs; minimal estimate
        monthly_cost = 16.2 if lb_type == "application" else 22.0

        req_avg = _cw_avg(cw, "AWS/ApplicationELB", "RequestCount",
                          [{"Name": "LoadBalancer", "Value": "/".join(lb_arn.split("/")[-3:])}])

        healthy = 0
        try:
            tgs = elbv2.describe_target_groups(LoadBalancerArn=lb_arn).get("TargetGroups", [])
            for tg in tgs:
                th = elbv2.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])
                healthy += sum(1 for t in th["TargetHealthDescriptions"]
                               if t["TargetHealth"]["State"] == "healthy")
        except Exception:
            pass

        suggestion = None
        saving = 0.0
        if healthy == 0:
            suggestion = "Delete idle load balancer (no healthy targets)"
            saving = monthly_cost

        resources.append({
            "service": "ELB",
            "resource_id": lb_name,
            "name": lb_name,
            "type": lb_type,
            "state": "active",
            "monthly_cost": monthly_cost,
            "healthy_targets": healthy,
            "request_avg": req_avg,
            "suggestion": suggestion,
            "potential_saving": saving,
            "region": region,
        })

    return resources


# ─── NAT Gateway ─────────────────────────────────────────────────────────────

def scan_nat_gateways(session, region):
    ec2 = session.client("ec2", region_name=region)
    cw  = session.client("cloudwatch", region_name=region)
    resources = []

    try:
        nats = ec2.describe_nat_gateways(
            Filters=[{"Name": "state", "Values": ["available"]}]
        ).get("NatGateways", [])
    except Exception:
        return resources

    for nat in nats:
        nat_id = nat["NatGatewayId"]
        name   = next((t["Value"] for t in nat.get("Tags", []) if t["Key"] == "Name"), nat_id)

        # NAT GW: $0.045/hr + $0.045/GB
        base_monthly = round(0.045 * HOURS_PER_MONTH, 2)

        bytes_out = _cw_sum(cw, "AWS/NATGateway", "BytesOutToDestination",
                            [{"Name": "NatGatewayId", "Value": nat_id}])
        gb_processed = round((bytes_out or 0) / (1024**3), 2)
        data_cost    = round(gb_processed * 0.045, 2)
        monthly_cost = round(base_monthly + data_cost, 2)

        resources.append({
            "service": "NAT Gateway",
            "resource_id": nat_id,
            "name": name,
            "type": "NAT",
            "state": "available",
            "monthly_cost": monthly_cost,
            "gb_processed": gb_processed,
            "suggestion": "Consider VPC endpoints to reduce NAT Gateway data costs" if gb_processed > 100 else None,
            "potential_saving": round(data_cost * 0.3, 2) if gb_processed > 100 else 0.0,
            "region": region,
        })

    return resources


# ─── S3 ──────────────────────────────────────────────────────────────────────

def scan_s3(session, region):
    s3  = session.client("s3")
    cw  = session.client("cloudwatch", region_name="us-east-1")  # S3 metrics in us-east-1
    resources = []

    try:
        buckets = s3.list_buckets().get("Buckets", [])
    except Exception:
        return resources

    for bucket in buckets:
        bname = bucket["Name"]
        size_bytes = _cw_avg(cw, "AWS/S3", "BucketSizeBytes",
                             [{"Name": "BucketName", "Value": bname},
                              {"Name": "StorageType", "Value": "StandardStorage"}])
        gb = round((size_bytes or 0) / (1024**3), 3)
        monthly_cost = round(gb * 0.023, 2)  # Standard storage

        resources.append({
            "service": "S3",
            "resource_id": bname,
            "name": bname,
            "type": "bucket",
            "state": "active",
            "size_gb": gb,
            "monthly_cost": monthly_cost,
            "suggestion": "Consider S3 Intelligent-Tiering for large buckets" if gb > 100 else None,
            "potential_saving": round(monthly_cost * 0.2, 2) if gb > 100 else 0.0,
            "region": "global",
        })

    return resources


# ─── VPC Components ─────────────────────────────────────────────────────────

def scan_subnets(session, region):
    ec2 = session.client("ec2", region_name=region)
    resources = []
    try:
        subnets = ec2.describe_subnets().get("Subnets", [])
        enis = ec2.describe_network_interfaces().get("NetworkInterfaces", [])
        used_subnet_ids = {eni["SubnetId"] for eni in enis}
        for sn in subnets:
            sn_id = sn["SubnetId"]
            name  = next((t["Value"] for t in sn.get("Tags", []) if t["Key"] == "Name"), sn_id)
            is_used = sn_id in used_subnet_ids
            resources.append({
                "service": "Subnet", "resource_id": sn_id, "name": name, "type": "subnet",
                "state": "active" if is_used else "unused (Zombie)", "monthly_cost": 0.0,
                "suggestion": "Delete unused subnet to simplify network architecture" if not is_used else None,
                "potential_saving": 0.0, "region": region,
            })
    except Exception: pass
    return resources

def scan_transit_gateways(session, region):
    ec2 = session.client("ec2", region_name=region)
    resources = []
    try:
        tgws = ec2.describe_transit_gateways().get("TransitGateways", [])
        for tgw in tgws:
            tgw_id = tgw["TransitGatewayId"]
            name   = next((t["Value"] for t in tgw.get("Tags", []) if t["Key"] == "Name"), tgw_id)
            monthly_cost = round(0.05 * 730, 2)
            attachments = ec2.describe_transit_gateway_attachments(
                Filters=[{"Name": "transit-gateway-id", "Values": [tgw_id]}]
            ).get("TransitGatewayAttachments", [])
            suggestion = "Delete idle Transit Gateway (no attachments)" if not attachments else None
            resources.append({
                "service": "Transit Gateway", "resource_id": tgw_id, "name": name, "type": "TGW",
                "state": tgw.get("State", "available"), "monthly_cost": monthly_cost,
                "attachments_count": len(attachments), "suggestion": suggestion,
                "potential_saving": monthly_cost if not attachments else 0.0, "region": region,
            })
    except Exception: pass
    return resources

def scan_vpc_peering(session, region):
    ec2 = session.client("ec2", region_name=region)
    resources = []
    try:
        peerings = ec2.describe_vpc_peering_connections().get("VpcPeeringConnections", [])
        for pc in peerings:
            pc_id = pc["VpcPeeringConnectionId"]
            state = pc.get("Status", {}).get("Code", "unknown")
            resources.append({
                "service": "VPC Peering", "resource_id": pc_id, "name": pc_id, "type": "peering",
                "state": state, "monthly_cost": 0.0,
                "suggestion": "Review cross-region transfer costs" if state == "active" else "Delete stale peering",
                "potential_saving": 0.0, "region": region,
            })
    except Exception: pass
    return resources


# ─── Additional Services (EKS, ECS, KDS, KFH) ────────────────────────────────

def scan_eks(session, region):
    eks = session.client("eks", region_name=region)
    resources = []
    try:
        clusters = eks.list_clusters().get("clusters", [])
    except Exception:
        return resources

    for cname in clusters:
        try:
            info = eks.describe_cluster(name=cname).get("cluster", {})
            state = info.get("status", "UNKNOWN")
            monthly_cost = round(0.10 * HOURS_PER_MONTH, 2)
            resources.append({
                "service": "EKS",
                "resource_id": cname,
                "name": cname,
                "type": "Cluster",
                "state": state,
                "monthly_cost": monthly_cost if state == "ACTIVE" else 0.0,
                "suggestion": None,
                "potential_saving": 0.0,
                "region": region,
            })
        except Exception:
            pass
    return resources

def scan_ecs(session, region):
    ecs = session.client("ecs", region_name=region)
    resources = []
    try:
        clusters = ecs.list_clusters().get("clusterArns", [])
    except Exception:
        return resources

    for c in clusters:
        try:
            info = ecs.describe_clusters(clusters=[c]).get("clusters", [])
            if not info:
                continue
            cinfo = info[0]
            cname = cinfo.get("clusterName", "Unknown")
            state = cinfo.get("status", "UNKNOWN")
            active_serv = cinfo.get("activeServicesCount", 0)
            task_cnt = cinfo.get("runningTasksCount", 0)
            
            suggestion = "Delete idle ECS cluster (0 running tasks, 0 active services)" if active_serv == 0 and task_cnt == 0 else None
            resources.append({
                "service": "ECS",
                "resource_id": cname,
                "name": cname,
                "type": "Cluster",
                "state": state,
                "monthly_cost": 0.0,
                "suggestion": suggestion,
                "potential_saving": 0.0,
                "region": region,
            })
        except Exception:
            pass
    return resources

def scan_kds(session, region):
    kinesis = session.client("kinesis", region_name=region)
    cw = session.client("cloudwatch", region_name=region)
    resources = []
    try:
        streams = kinesis.list_streams().get("StreamNames", [])
    except Exception:
        return resources

    for sname in streams:
        try:
            info = kinesis.describe_stream_summary(StreamName=sname).get("StreamDescriptionSummary", {})
            state = info.get("StreamStatus", "UNKNOWN")
            shards = info.get("OpenShardCount", 1)
            monthly_cost = round(0.015 * shards * HOURS_PER_MONTH, 2)
            incoming = _cw_sum(cw, "AWS/Kinesis", "IncomingBytes", [{"Name": "StreamName", "Value": sname}])
            
            suggestion = "Consider deleting idle Kinesis stream (0 incoming bytes)" if (incoming is not None and incoming == 0) else None
            saving = monthly_cost if (incoming is not None and incoming == 0) else 0.0
            
            resources.append({
                "service": "KDS",
                "resource_id": sname,
                "name": sname,
                "type": "Stream",
                "state": state,
                "monthly_cost": monthly_cost,
                "suggestion": suggestion,
                "potential_saving": saving,
                "region": region,
            })
        except Exception:
            pass
    return resources

def scan_kfh(session, region):
    firehose = session.client("firehose", region_name=region)
    cw = session.client("cloudwatch", region_name=region)
    resources = []
    try:
        streams = firehose.list_delivery_streams().get("DeliveryStreamNames", [])
    except Exception:
        return resources

    for sname in streams:
        try:
            info = firehose.describe_delivery_stream(DeliveryStreamName=sname).get("DeliveryStreamDescription", {})
            state = info.get("DeliveryStreamStatus", "UNKNOWN")
            
            incoming_bytes = _cw_sum(cw, "AWS/Firehose", "IncomingBytes", [{"Name": "DeliveryStreamName", "Value": sname}])
            gb_in = (incoming_bytes or 0) / (1024**3)
            monthly_cost = round(gb_in * 0.029, 2)
            
            resources.append({
                "service": "KFH",
                "resource_id": sname,
                "name": sname,
                "type": "DeliveryStream",
                "state": state,
                "monthly_cost": monthly_cost,
                "suggestion": None,
                "potential_saving": 0.0,
                "region": region,
            })
        except Exception:
            pass
    return resources


# ─── Master scanner ──────────────────────────────────────────────────────────

def scan_all_resources(session, region):
    """
    Run all service scanners and return:
      - resources: flat list of resource dicts
      - summary: cost totals by service
    """
    scanners = [
        ("EC2",         lambda: scan_ec2(session, region)),
        ("EBS",         lambda: scan_ebs(session, region)),
        ("RDS",         lambda: scan_rds(session, region)),
        ("Elastic IP",  lambda: scan_elastic_ips(session, region)),
        ("ELB",         lambda: scan_elb(session, region)),
        ("NAT Gateway", lambda: scan_nat_gateways(session, region)),
        ("S3",          lambda: scan_s3(session, region)),
        ("Subnet",      lambda: scan_subnets(session, region)),
        ("TGW",         lambda: scan_transit_gateways(session, region)),
        ("VPCPeering",  lambda: scan_vpc_peering(session, region)),
        ("EKS",         lambda: scan_eks(session, region)),
        ("ECS",         lambda: scan_ecs(session, region)),
        ("KDS",         lambda: scan_kds(session, region)),
        ("KFH",         lambda: scan_kfh(session, region)),
    ]

    all_resources = []
    errors = []

    for name, fn in scanners:
        try:
            results = fn()
            all_resources.extend(results)
        except botocore.exceptions.ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("AccessDenied", "AccessDeniedException"):
                errors.append(f"{name}: Access denied")
            else:
                errors.append(f"{name}: {str(e)}")
        except Exception as e:
            errors.append(f"{name}: {str(e)}")

    # Aggregate summary by service
    summary = {}
    for r in all_resources:
        svc = r["service"]
        if svc not in summary:
            summary[svc] = {"count": 0, "total_cost": 0.0, "total_saving": 0.0}
        summary[svc]["count"] += 1
        summary[svc]["total_cost"]   += r.get("monthly_cost", 0) or 0
        summary[svc]["total_saving"] += r.get("potential_saving", 0) or 0

    for svc in summary:
        summary[svc]["total_cost"]   = round(summary[svc]["total_cost"], 2)
        summary[svc]["total_saving"] = round(summary[svc]["total_saving"], 2)

    total_cost   = round(sum(r.get("monthly_cost", 0) or 0 for r in all_resources), 2)
    total_saving = round(sum(r.get("potential_saving", 0) or 0 for r in all_resources), 2)
    score = max(0, min(100, round(100 - (total_saving / max(total_cost, 1)) * 100)))

    # Fetch TRUE Total Billed Cost via Cost Explorer
    actual_ce_cost = 0.0
    try:
        ce = session.client('ce')
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        ce_resp = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost']
        )
        if ce_resp.get("ResultsByTime"):
            val = ce_resp["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]
            actual_ce_cost = round(float(val), 2)
    except Exception as e:
        actual_ce_cost = total_cost  # Fallback gracefully if CE disabled or permissions lacking

    return {
        "resources": all_resources,
        "summary": summary,
        "total_cost": total_cost,
        "actual_30d_ce_cost": actual_ce_cost,
        "total_saving": total_saving,
        "optimization_score": score,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
    }
