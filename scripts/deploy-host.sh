#!/bin/bash
# Run as root through SSM. Arguments contain no secrets.
set -euo pipefail
ENVIRONMENT=$1; REGION=$2; IMAGE=$3; VOLUME=$4
[[ "$ENVIRONMENT" =~ ^(dev|production)$ ]]
[[ "$REGION" =~ ^[a-z]{2}-[a-z]+-[0-9]$ ]]
[[ "$IMAGE" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/autoapp@sha256:[a-f0-9]{64}$ ]]
[[ "$VOLUME" =~ ^vol-[a-f0-9]+$ ]]
exec 9>/var/lock/autoapp-deploy.lock
flock -w 600 9
systemctl is-active --quiet docker
install -d -m 0750 /opt/autoapp
SERIAL=${VOLUME//-/}
DEVICE=""
for attempt in $(seq 1 60); do
  DEVICE=$(lsblk -dnpo NAME,SERIAL | awk -v serial="$SERIAL" '$2 == serial {print $1}')
  [[ -n "$DEVICE" ]] && break
  sleep 5
done
[[ -b "$DEVICE" ]] || { echo 'Attached EBS data volume not found'; exit 1; }
# Refuse disks with partitions; format only the exact new, blank EBS disk.
[[ $(lsblk -n "$DEVICE" | wc -l) -eq 1 ]]
if ! blkid "$DEVICE" >/dev/null; then
  [[ -z $(wipefs -n --noheadings "$DEVICE") ]]
  mkfs.xfs "$DEVICE"
fi
[[ $(blkid -s TYPE -o value "$DEVICE") == xfs ]]
UUID=$(blkid -s UUID -o value "$DEVICE")
if ! mountpoint -q /opt/autoapp/data; then
  install -d /opt/autoapp/data
  mount -U "$UUID" /opt/autoapp/data
fi
[[ $(findmnt -n -o UUID --target /opt/autoapp/data) == "$UUID" ]]
grep -q "UUID=$UUID " /etc/fstab || echo "UUID=$UUID /opt/autoapp/data xfs defaults,nofail 0 2" >> /etc/fstab
install -d /etc/systemd/system/docker.service.d
printf '[Unit]\nRequiresMountsFor=/opt/autoapp/data\n' > /etc/systemd/system/docker.service.d/autoapp-data.conf
systemctl daemon-reload
systemctl try-restart amazon-cloudwatch-agent
chown 1000:1000 /opt/autoapp/data
chmod 0700 /opt/autoapp/data
REGISTRY=${IMAGE%%/*}
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker pull "$IMAGE"
OLD=$(docker inspect --format '{{.Config.Image}}' autoapp 2>/dev/null || true)
run_image() {
  docker run -d --name autoapp --restart unless-stopped \
    --user 1000:1000 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=128m --memory 1536m --cpus 1.5 \
    -p 5080:5080 -v /opt/autoapp/data:/app/data \
    -e DEPLOY_ENV="$ENVIRONMENT" -e AWS_AUTH_MODE=instance-role -e AWS_DEFAULT_REGION="$REGION" \
    --log-driver awslogs --log-opt awslogs-region="$REGION" \
    --log-opt awslogs-group="/autoapp/$ENVIRONMENT" --log-opt awslogs-stream="portal" "$1"
}
healthy() {
  for attempt in $(seq 1 30); do
    [[ $(docker inspect --format '{{.State.Health.Status}}' autoapp 2>/dev/null) == healthy ]] && return 0
    sleep 5
  done
  return 1
}
# Stop writes before a SQLite online backup. Do not copy a live WAL database.
if [[ -n "$OLD" ]]; then
  docker stop -t 45 autoapp
  if ! docker run --rm --user 1000:1000 --network none --entrypoint python \
    -v /opt/autoapp/data:/app/data "$OLD" -c \
    "import sqlite3; s=sqlite3.connect('/app/data/portal.db'); d=sqlite3.connect('/app/data/pre-release.db'); s.backup(d); d.close(); s.close()"; then
    docker start autoapp
    echo 'Backup failed; existing container restarted'
    exit 1
  fi
  docker rm autoapp
fi
if run_image "$IMAGE" && healthy; then
  printf '%s\n' "$IMAGE" > /opt/autoapp/current-image
  echo 'Deployment healthy'
else
  docker rm -f autoapp || true
  if [[ -n "$OLD" ]]; then
    # Code rollback only. Never silently revert data after a schema migration.
    run_image "$OLD"
    healthy || echo 'CRITICAL: rollback unhealthy; operator intervention required'
  fi
  exit 1
fi
