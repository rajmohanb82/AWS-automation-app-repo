# Keep the database across Render rebuilds

CloudSync stores accounts, sign-in, AWS connection details, and scan history in one SQLite file: `/var/data/portal.db`.

A Render rebuild replaces the container filesystem. Anything written outside a persistent disk is deleted, and the next start creates an empty database. That is why setup appears again after every deploy.

Add the disk to the web service that is already deployed. The application code stays as it is. These steps are only in the Render dashboard.

## 1. Use a paid instance

Open the web service in the Render dashboard. If the instance type is Free, open **Settings**, change **Instance type** to **Starter** (or any paid type), and save.

Render does not attach persistent disks to free instances. The database on a free instance is erased on every rebuild.

## 2. Add the disk

In the same service, open **Disks** in the left sidebar, then **Add disk**.

| Field | Value |
| --- | --- |
| Name | `portal-data` |
| Mount path | `/var/data` |
| Size | `1` GB |

Save the disk. Render redeploys the service and mounts an empty disk at `/var/data`.

Use that mount path exactly. The image reads the database from `/var/data/portal.db`. A different path leaves the file on the temporary filesystem, and the next rebuild starts setup again.

## 3. Set the database path

Open **Environment** and set:

| Key | Value |
| --- | --- |
| `HOST` | `0.0.0.0` |
| `PORTAL_DB` | `/var/data/portal.db` |
| `PYTHONUNBUFFERED` | `1` |

Leave `PORT` unset. Save the changes if Render did not already restart for the new disk.

The Dockerfile sets the same values. Setting them in the dashboard keeps the file on the disk even if the start command is edited later.

## 4. Finish setup once

Open the service URL after this deploy and complete setup again. The database that existed before the disk was attached was on the temporary filesystem and is already gone. This new file is the one that remains.

## 5. Confirm the next rebuild keeps it

Open **Logs** for the deploy that added the disk. The first start on the new disk prints:

```text
CloudSync database: /var/data/portal.db
No database file on the persistent disk yet. Setup will create one.
```

After setup, choose **Manual Deploy** → **Deploy latest commit**. The new logs should print:

```text
CloudSync database: /var/data/portal.db
Existing database found on the persistent disk. Keeping it.
```

Sign in with the same account. If setup appears again, the disk is missing or `PORTAL_DB` does not point at `/var/data/portal.db`.

## What the disk keeps

The disk survives rebuilds, restarts, and crashes. It holds:

- `/var/data/portal.db`
- the SQLite sidecar files `/var/data/portal.db-wal` and `/var/data/portal.db-shm`

Leave all three on the disk. Do not point `PORTAL_DB` at `/app` or `portal/data`. Those directories are replaced when Render builds a new image.

## Limits

- Keep this service at one instance. Render does not share a disk between instances.
- Do not change the mount path later. Render treats a new path as a new empty disk.
- Do not delete the disk. Deleting it deletes the accounts and scan history.
- Deleting the web service deletes its disk.
- Disk size can be increased later. It cannot be reduced.
- The disk does not copy `portal/data/portal.db` from your computer. Setup on Render is a separate database.
