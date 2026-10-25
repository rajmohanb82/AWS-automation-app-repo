# Operations console

One console for AWS housekeeping, cost advice, and governance. The first launch asks whether this installation is an MSP (customers and accounts) or a product company (one or many products, each with environments such as development and production).

## Run

Docker, from the repository root:

```bash
docker compose up -d --build
```

Open http://127.0.0.1:5080 and complete setup. The administrator enrolls an authenticator app at first sign-in. The database stays in `portal/data`. AWS profiles on this machine are visible inside the container from `~/.aws`.

Without Docker:

```bash
cd portal
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

Server install: `sudo ./deploy.sh` places the app in `/opt/cloud-ops-portal` and starts `portal.service` on port 5080.

## Sign-in and AWS access

Settings keeps these separate:

- **Local accounts** use a password and a TOTP authenticator. Administrators create every account.
- **Identity provider** (OIDC) can be enabled beside local accounts. The provider must release `email` and `profile`. An optional group claim grants administrator.
- **Scans** use either a local AWS profile on the console machine, or IAM Identity Center. If an account's ID differs from the connected identity, the console assumes that account's role.

## Advice

Cost recommendations come from [Cost Optimization Hub](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html), which includes the account's discounts. If the hub is unavailable, the console uses Compute Optimizer. Inventory estimates are labeled separately and use published on-demand prices. There is no general-purpose language model in the advice path.

Trusted Advisor summaries appear on the governance page when the account's support plan allows the API. Business Support+ is the minimum plan for that API.

Housekeeping fixes change live resources and are limited to administrators.

## Later integrations

Each scan and remediation writes an integration event (finding id, account, region, outcome). Those rows are visible under Audit. Delivery to MSPOPS or an ITSM tool is not connected yet.

## Prior version

`housekeeping-app/`, `cost-optimizer/`, `admin-panel/`, and `auth/` are the previous three-app layout for the earlier organization. This console replaces that layout.

## AWS CI/CD project

See [docs/PROJECT1.md](docs/PROJECT1.md) for the coordinated two-repository deployment project.
