# AWS Cost Optimizer — Local Deployment Guide

## Orient Technologies | Internal Documentation

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Setup AWS Access Keys](#step-1-setup-aws-access-keys)
4. [Step 2: Create IAM Role in Client Account](#step-2-create-iam-role-in-client-account)
5. [Step 3: Install Python Dependencies](#step-3-install-python-dependencies)
6. [Step 4: Configure Client Accounts](#step-4-configure-client-accounts)
7. [Step 5: Run the Application](#step-5-run-the-application)
8. [Step 6: Access the Application](#step-6-access-the-application)
9. [Adding New Client Accounts](#adding-new-client-accounts)
10. [Removing Client Accounts](#removing-client-accounts)
11. [Troubleshooting](#troubleshooting)
12. [File Structure](#file-structure)

---

## Overview

This is the **local/laptop version** of the AWS Cost Optimizer. It runs on your Windows machine and uses an AWS IAM profile (access keys) to assume role into client accounts for scanning.

### How It Works

```
Your Laptop (Windows)
    |
    |-- AWS Profile: CloudOps_Tutorial_Hub (access keys in ~/.aws/credentials)
    |
    |-- App runs on: http://localhost:5001
    |
    +-- STS AssumeRole --> Client Accounts (from accounts.json)
                              |
                              |-- Client A (433222279698)
                              |-- Client B (111111111111)
                              +-- Client C (222222222222)
```

---

## Prerequisites

1. **Python 3.11+** installed on your laptop
2. **AWS CLI** installed
3. **AWS Access Keys** configured for your tooling account
4. **IAM Role** (`CostOptimizerReadOnly`) created in each client account

---

## Step 1: Setup AWS Access Keys

### 1.1 Configure AWS Profile

Run:

```cmd
aws configure --profile CloudOps_Tutorial_Hub
```

Enter:
```
AWS Access Key ID: <your-access-key>
AWS Secret Access Key: <your-secret-key>
Default region name: ap-south-1
Default output format: json
```

### 1.2 Verify

```cmd
aws sts get-caller-identity --profile CloudOps_Tutorial_Hub
```

Expected output:
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "746669191484",
    "Arn": "arn:aws:iam::746669191484:user/YourUser"
}
```

### 1.3 IAM Permissions for Your User

Your IAM user in the tooling account needs this permission:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::*:role/CostOptimizerReadOnly"
    }
  ]
}
```

---

## Step 2: Create IAM Role in Client Account

**Repeat this in every client account you want to scan.**

### 2.1 Go to IAM -> Roles -> Create Role in the client account

- **Trusted entity type:** Another AWS Account
- **Account ID:** Enter your tooling account ID (e.g., `746669191484`)

### 2.2 Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::746669191484:root"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 2.3 Permissions

Attach `ReadOnlyAccess` (AWS managed policy)

Or custom minimal policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "rds:Describe*",
        "elasticloadbalancing:Describe*",
        "cloudwatch:GetMetricStatistics",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation",
        "eks:ListClusters",
        "eks:DescribeCluster",
        "ecs:ListClusters",
        "ecs:DescribeClusters",
        "kinesis:List*",
        "kinesis:DescribeStreamSummary",
        "firehose:List*",
        "firehose:DescribeDeliveryStream",
        "ce:GetCostAndUsage",
        "pricing:GetProducts"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2.4 Role Name

**Name:** `CostOptimizerReadOnly`

### 2.5 Verify AssumeRole Works

```cmd
aws sts assume-role --role-arn "arn:aws:iam::<CLIENT_ACCOUNT_ID>:role/CostOptimizerReadOnly" --role-session-name "test" --profile CloudOps_Tutorial_Hub
```

If you get credentials back, it works!

---

## Step 3: Install Python Dependencies

Open Command Prompt and run:

```cmd
cd C:\Users\akash\Downloads\housekeep-costoptimize-aws-dev\housekeep-costoptimize-aws-dev\cost_optimizer
pip install -r requirements.txt
```

---

## Step 4: Configure Client Accounts

Edit the file `accounts.json` in the `cost_optimizer` folder:

```json
[
  {"account_id": "433222279698", "name": "Test Client Account", "role_name": "CostOptimizerReadOnly"},
  {"account_id": "111111111111", "name": "Client B - Production", "role_name": "CostOptimizerReadOnly"},
  {"account_id": "222222222222", "name": "Client C - Staging", "role_name": "CostOptimizerReadOnly"}
]
```

Each entry has:
- `account_id` — The AWS account ID of the client
- `name` — Friendly name (shown in dropdown)
- `role_name` — IAM role name in that account (usually `CostOptimizerReadOnly`)

---

## Step 5: Run the Application

```cmd
cd C:\Users\akash\Downloads\housekeep-costoptimize-aws-dev\housekeep-costoptimize-aws-dev\cost_optimizer
python app.py
```

Expected output:
```
AWS Cost Optimizer starting at http://127.0.0.1:5001
 * Serving Flask app 'app'
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5001
```

> Keep this terminal open while using the app. Press Ctrl+C to stop.

---

## Step 6: Access the Application

Open your browser:

```
http://localhost:5001
```

### Usage Flow:

1. Select **AWS Region** from dropdown
2. Select **Client Account** from dropdown (shows names from accounts.json)
3. Click **Connect** — app assumes role into that account
4. Click **Analyze Costs** — scans all resources (takes 30-60 seconds)
5. View dashboard with charts, recommendations, heatmaps
6. Export as **PDF** or **XLSX**

---

## Adding New Client Accounts

### When a new client needs to be added:

**Step 1:** Create `CostOptimizerReadOnly` role in the new client's AWS account (see [Step 2](#step-2-create-iam-role-in-client-account))

**Step 2:** Verify AssumeRole works:
```cmd
aws sts assume-role --role-arn "arn:aws:iam::<NEW_ACCOUNT_ID>:role/CostOptimizerReadOnly" --role-session-name "test" --profile CloudOps_Tutorial_Hub
```

**Step 3:** Edit `accounts.json` — add the new entry:

Before:
```json
[
  {"account_id": "433222279698", "name": "Test Client Account", "role_name": "CostOptimizerReadOnly"}
]
```

After:
```json
[
  {"account_id": "433222279698", "name": "Test Client Account", "role_name": "CostOptimizerReadOnly"},
  {"account_id": "999888777666", "name": "New Client - Production", "role_name": "CostOptimizerReadOnly"}
]
```

> IMPORTANT: Make sure the JSON is valid — check commas between entries!

**Step 4:** Restart the app:
- Press `Ctrl+C` in the terminal to stop
- Run `python app.py` again

**Step 5:** Refresh browser — new client appears in dropdown.

---

## Removing Client Accounts

**Step 1:** Edit `accounts.json` — remove the entry

**Step 2:** Restart the app (Ctrl+C then `python app.py`)

**Step 3:** (Optional) Delete the `CostOptimizerReadOnly` role from the client's AWS account

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Unable to locate credentials" | AWS profile not configured | Run `aws configure --profile CloudOps_Tutorial_Hub` |
| "AssumeRole failed: AccessDenied" | Trust policy doesn't trust your account | Check trust policy in client's role |
| "ModuleNotFoundError" | Python packages not installed | Run `pip install -r requirements.txt` |
| App won't start | Port 5001 already in use | Kill other process: `netstat -ano | findstr :5001` then `taskkill /PID <pid> /F` |
| "Account not found in accounts.json" | Account not added to config | Edit `accounts.json` |
| PDF generation fails | Missing matplotlib | Run `pip install matplotlib numpy` |
| Scan takes too long | Many resources or slow network | Wait — large accounts can take 1-2 minutes |
| Browser shows nothing | App not running | Check terminal — run `python app.py` |

---

## Changing the Tooling Profile

If your AWS profile name is different from `CloudOps_Tutorial_Hub`, edit `app.py`:

Find this line:
```python
TOOLING_PROFILE = os.environ.get("AWS_PROFILE", "CloudOps_Tutorial_Hub")
```

Change `CloudOps_Tutorial_Hub` to your profile name.

Or set environment variable before running:
```cmd
set AWS_PROFILE=YourProfileName
python app.py
```

---

## File Structure

```
cost_optimizer/
|-- app.py                 # Main Flask application (uses access key profile)
|-- scanner.py             # AWS resource scanner (14 services)
|-- ai_advisor.py          # AI recommendation engine (GPT-4o or rules)
|-- accounts.json          # Client accounts list <-- EDIT THIS
|-- requirements.txt       # Python dependencies
|-- static/
|   |-- cost_app.js        # Frontend JavaScript
|   +-- cost_style.css     # Frontend styles
|-- templates/
|   +-- index.html         # Dashboard HTML
+-- docs/
    +-- Local_Deployment_Guide.md  # This document
```

Parent directory also contains:
```
pdf_generator.py           # PDF report generator with charts
```

---

## Quick Reference

| Task | Action |
|------|--------|
| Start app | `python app.py` |
| Stop app | `Ctrl+C` in terminal |
| Add client | Edit `accounts.json` -> restart app |
| Remove client | Remove from `accounts.json` -> restart app |
| Change region | Select from dropdown in browser |
| Export report | Click "Download PDF Report" or "Export XLSX" in dashboard |
| Enable AI (GPT-4o) | Set env: `set OPENAI_API_KEY=sk-...` before running |

---

## Security Notes

1. **Access keys** are stored in `~/.aws/credentials` — never share this file
2. **Client accounts** only have read-only access — app cannot modify resources
3. **No credentials in code** — `accounts.json` only has account IDs, no secrets
4. **Local only** — app runs on localhost, not accessible from outside

---

## Contact

For issues or questions, contact the Cloud Operations team.

**Document Version:** 1.0
**Last Updated:** May 2026
**Author:** Orient Technologies — Cloud Operations
