#!/bin/sh
# Render mounts the persistent disk as root after the image is built.
# Make that directory writable, then run the console as the app user.
set -eu

db_path="${PORTAL_DB:-/var/data/portal.db}"
db_dir=$(dirname "$db_path")
mkdir -p "$db_dir"

echo "CloudSync database: $db_path"
if [ -f "$db_path" ]; then
    echo "Existing database found on the persistent disk. Keeping it."
else
    echo "No database file on the persistent disk yet. Setup will create one."
fi

if [ "$(id -u)" = "0" ]; then
    chown -R app:app "$db_dir"
    exec runuser -u app -- "$@"
fi

exec "$@"
