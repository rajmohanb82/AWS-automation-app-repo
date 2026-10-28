#!/bin/sh
# Render mounts the persistent disk as root after the image is built.
# Make that directory writable, then run the console as the app user.
set -eu

db_dir=$(dirname "${PORTAL_DB:-/var/data/portal.db}")
mkdir -p "$db_dir"

if [ "$(id -u)" = "0" ]; then
    chown -R app:app "$db_dir"
    exec runuser -u app -- "$@"
fi

exec "$@"
