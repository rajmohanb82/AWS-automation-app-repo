#!/bin/bash
set -euo pipefail
echo "Installing the operations console..."

TARGET=/opt/cloud-ops-portal
mkdir -p "$TARGET/data"
(
  cd portal
  tar --exclude .venv --exclude __pycache__ --exclude '*.db' --exclude data -cf - .
) | tar -C "$TARGET" -xf -
python3 -m venv "$TARGET/.venv"
"$TARGET/.venv/bin/pip" install -r "$TARGET/requirements.txt"
cp systemd/portal.service /etc/systemd/system/portal.service
systemctl daemon-reload
systemctl enable --now portal.service
systemctl restart portal.service

echo ""
echo "Console: http://127.0.0.1:5080"
echo "Open /setup on first launch and create the administrator there."
