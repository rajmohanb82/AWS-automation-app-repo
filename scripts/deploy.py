"""Submit the reviewed host script to SSM and wait for its actual result."""
import base64
import os
import re
import shlex
import time
from pathlib import Path
import boto3

region = os.environ["AWS_REGION"]
environment = os.environ["DEPLOY_ENV"]
instance = os.environ["INSTANCE_ID"]
volume = os.environ["DATA_VOLUME_ID"]
image = os.environ["IMAGE"]
assert environment in {"dev", "production"}
assert re.fullmatch(r"i-[a-f0-9]+", instance)
assert re.fullmatch(r"vol-[a-f0-9]+", volume)
assert re.fullmatch(r"[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/autoapp@sha256:[a-f0-9]{64}", image)
ec2 = boto3.client("ec2", region_name=region)
row = ec2.describe_instances(InstanceIds=[instance])["Reservations"][0]["Instances"][0]
tags = {x["Key"]: x["Value"] for x in row.get("Tags", [])}
assert tags.get("Environment") == environment and tags.get("Project") == "autoapp"
vol = ec2.describe_volumes(VolumeIds=[volume])["Volumes"][0]
assert any(a["InstanceId"] == instance for a in vol["Attachments"])
ssm = boto3.client("ssm", region_name=region)
script = base64.b64encode(Path("scripts/deploy-host.sh").read_bytes()).decode()
command = "set -eu; echo " + shlex.quote(script) + " | base64 -d > /opt/autoapp-deploy.sh; bash /opt/autoapp-deploy.sh " + " ".join(map(shlex.quote, [environment, region, image, volume]))
cid = ssm.send_command(InstanceIds=[instance], DocumentName="AWS-RunShellScript", Parameters={"commands": [command], "executionTimeout": ["1200"]}, TimeoutSeconds=120)["Command"]["CommandId"]
print("SSM command:", cid, flush=True)
for _ in range(150):
    time.sleep(10)
    try:
        result = ssm.get_command_invocation(CommandId=cid, InstanceId=instance)
    except ssm.exceptions.InvocationDoesNotExist:
        continue
    status = result["Status"]
    if status in {"Pending", "InProgress", "Delayed"}:
        continue
    print(result.get("StandardOutputContent", ""))
    print(result.get("StandardErrorContent", ""))
    if status != "Success":
        raise SystemExit("Deployment failed: " + status)
    break
else:
    raise SystemExit("Timed out waiting for SSM")
elb = boto3.client("elbv2", region_name=region)
for _ in range(30):
    states = elb.describe_target_health(TargetGroupArn=os.environ["TARGET_GROUP_ARN"], Targets=[{"Id": instance, "Port": 5080}])["TargetHealthDescriptions"]
    if states and states[0]["TargetHealth"]["State"] == "healthy":
        break
    time.sleep(10)
else:
    raise SystemExit("Container is running but ALB target is unhealthy; inspect listener, SG and application logs")
ssm.put_parameter(Name=f"/autoapp/{environment}/deployed-digest", Type="String", Value=image.split("@", 1)[1], Overwrite=True)
print("Deployment and ALB health verified")
