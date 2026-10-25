"""Stable finding ids, documentation links, and governance pillars."""

import hashlib
import json

import db

DOC_LINKS = (
    ("Without MFA", "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa.html"),
    ("Access Key", "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html"),
    ("Inactive IAM", "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_finding-unused.html"),
    ("Public Access", "https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html"),
    ("Versioning", "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html"),
    ("Open to World", "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html"),
    ("Unused Security Group", "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html"),
    ("Flow Logs", "https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html"),
    ("Default VPC", "https://docs.aws.amazon.com/vpc/latest/userguide/default-vpc.html"),
    ("NAT Gateway", "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html"),
    ("Stopped EC2", "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html"),
    ("Unattached EBS", "https://docs.aws.amazon.com/ebs/latest/userguide/ebs-deleting-volume.html"),
    ("Elastic IP", "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html"),
    ("Publicly Accessible", "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html"),
    ("Stopped RDS", "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html"),
    ("Load Balancer", "https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/load-balancer-delete.html"),
    ("Lambda", "https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics.html"),
    ("INSUFFICIENT_DATA", "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html"),
    ("EKS", "https://docs.aws.amazon.com/eks/latest/userguide/clusters.html"),
    ("ECS", "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html"),
    ("Encryption", "https://docs.aws.amazon.com/streams/latest/dev/server-side-encryption.html"),
    ("Firehose", "https://docs.aws.amazon.com/firehose/latest/dev/encryption.html"),
)

SERVICE_DOCS = {
    "EC2": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-recommendations.html",
    "EBS": "https://docs.aws.amazon.com/ebs/latest/userguide/ebs-optimize.html",
    "RDS": "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html",
    "Elastic IP": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html",
    "ELB": "https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/load-balancer-delete.html",
    "NAT Gateway": "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html",
    "S3": "https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering.html",
    "Subnet": "https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html",
    "Transit Gateway": "https://docs.aws.amazon.com/vpc/latest/tgw/what-is-transit-gateway.html",
    "VPC Peering": "https://docs.aws.amazon.com/vpc/latest/peering/what-is-vpc-peering.html",
    "EKS": "https://docs.aws.amazon.com/eks/latest/userguide/cost-optimization.html",
    "ECS": "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-best-practices.html",
    "KDS": "https://docs.aws.amazon.com/streams/latest/dev/kinesis-tutorial-cli.html",
    "KFH": "https://docs.aws.amazon.com/firehose/latest/dev/what-is-this-service.html",
}

PILLARS = (
    "Security",
    "Reliability",
    "Cost optimization",
    "Operational excellence",
    "Performance",
)


def finding_id(account_id, region, category, title, resource_id):
    raw = "|".join([account_id or "", region or "", category or "", title or "", resource_id or ""])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def documentation_url(title):
    for needle, url in DOC_LINKS:
        if needle.lower() in (title or "").lower():
            return url
    return "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"


def pillar_for(finding):
    title = finding.get("title") or ""
    category = finding.get("category") or ""
    if any(word in title for word in ("NAT", "Stopped", "Unattached", "Unused Elastic", "Idle")):
        return "Cost optimization"
    if category in {"IAM", "S3", "Security Groups", "KDS", "KFH"}:
        return "Security"
    if category == "RDS":
        return "Security" if "Public" in title else "Cost optimization"
    if category == "VPC":
        return "Reliability" if "Flow" in title else "Security"
    if category == "CloudWatch":
        return "Operational excellence"
    if category in {"Lambda", "EKS", "ECS"}:
        return "Performance"
    if category == "EC2":
        return "Cost optimization"
    return "Operational excellence"


def decorate_finding(finding, account_id, region):
    item = dict(finding)
    item["finding_id"] = finding_id(
        account_id, region, item.get("category"), item.get("title"), item.get("resource_id")
    )
    item["documentation_url"] = documentation_url(item.get("title"))
    item["pillar"] = pillar_for(item)
    item["account_id"] = account_id
    item["region"] = region
    return item


def record_scan(kind, account, region, actor, findings):
    counts = {}
    ids = []
    for finding in findings:
        severity = finding.get("severity") or finding.get("priority") or "INFO"
        counts[severity] = counts.get(severity, 0) + 1
        if finding.get("finding_id"):
            ids.append(finding["finding_id"])
    summary = {
        "counts": counts,
        "total": len(findings),
        "account_id": account["account_id"],
        "account_name": account["name"],
        "region": region,
    }
    db.add_scan(kind, account["account_id"], account["name"], region, actor, json.dumps(summary))
    db.add_event(
        "scan.completed",
        json.dumps(
            {
                "scan_kind": kind,
                "account_id": account["account_id"],
                "account_name": account["name"],
                "region": region,
                "actor": actor,
                "counts": counts,
                "finding_ids": ids[:500],
                "finding_total": len(ids),
            }
        ),
    )
    return summary
