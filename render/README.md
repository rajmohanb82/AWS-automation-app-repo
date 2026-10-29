# Deploy CloudSync on Render

This folder is only for [Render](https://render.com). The Docker Compose setup at the repository root is unchanged and remains the way to run the console on your own machine.

Render runs one Docker web service. It does not read `docker-compose.yml`.

## What gets deployed

The image is built from `portal/` with `render/Dockerfile`. Gunicorn listens on the port Render assigns (`PORT`) and on all interfaces. The SQLite database is stored at `/var/data/portal.db` on a persistent disk, so accounts, sign-in, and scan history survive a redeploy.

The local database in `portal/data` is not copied into the image. Render also erases the container filesystem on every rebuild. Accounts and scan history stay only when a persistent disk is mounted at `/var/data` and `PORTAL_DB` is `/var/data/portal.db`.

If the live service asks for setup again after each deploy, follow [PERSISTENT-DATABASE.md](PERSISTENT-DATABASE.md). Add the disk to the service that is already running. Do not create a second service.

## Deploy with the blueprint

1. Push this repository to GitHub or GitLab.
2. In the Render dashboard, choose **New** → **Blueprint**.
3. Select the repository. If Render asks for the blueprint file, set it to `render/render.yaml`.
4. Apply the blueprint. Render creates a web service named `cloudsync` in Singapore, on the Starter plan, with a 1 GB disk mounted at `/var/data`.
5. Open the service URL (for example `https://cloudsync.onrender.com`) and finish setup.

A disk requires a paid instance. The blueprint uses the Starter plan for that reason. The free instance type has no disk, so the database would be erased every time the service restarts.

## Deploy without the blueprint

Create a **Web Service**, choose the repository, and set:

| Setting | Value |
| --- | --- |
| Language / runtime | Docker |
| Dockerfile path | `render/Dockerfile` |
| Docker build context | `.` (repository root) |
| Health check path | `/healthz` |
| Instance type | Starter or higher |

Add a disk named `portal-data`, mounted at `/var/data`, 1 GB or larger. Then add these environment variables:

| Key | Value |
| --- | --- |
| `HOST` | `0.0.0.0` |
| `PORTAL_DB` | `/var/data/portal.db` |
| `PYTHONUNBUFFERED` | `1` |

Leave `PORT` unset. Render sets it.

## AWS access

This service has no copy of the `~/.aws` folder from your computer. After setup, open **Settings** and connect with IAM Identity Center, or with access keys stored by the console. Scans run from Render's network, so the AWS account must allow that connection.

## Phone app

In the Android app, set the console address to the Render URL, including `https://`.

## Check the image locally

From the repository root, without using Compose:

```bash
docker build -f render/Dockerfile -t cloudsync-render .
docker run --rm -p 5081:10000 -e PORT=10000 cloudsync-render
```

Open `http://127.0.0.1:5081/healthz`. Stop that container when you are finished. It does not replace the Compose service on port 5080.
