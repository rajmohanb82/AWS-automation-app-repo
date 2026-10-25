# AWS Cost Optimizer — EC2 Deployment Guide

## Orient Technologies | Internal Documentation

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Create IAM Role in Tooling Account](#step-1-create-iam-role-in-tooling-account)
4. [Step 2: Create IAM Role in Each Client Account](#step-2-create-iam-role-in-each-client-account)
5. [Step 3: Launch EC2 Instance](#step-3-launch-ec2-instance)
6. [Step 4: Deploy Application on EC2](#step-4-deploy-application-on-ec2)
7. [Step 5: Create Systemd Service](#step-5-create-systemd-service)
8. [Step 6: Add Client Accounts](#step-6-add-client-accounts)
9. [Step 7: Access the Application](#step-7-access-the-application)
10. [Step 8: Production Hardening (Optional)](#step-8-production-hardening-optional)
11. [Day-to-Day Operations](#day-to-day-operations)
12. [Automation: Deploy Role to Multiple Accounts](#automation-deploy-role-to-multiple-accounts)
13. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Tooling Account (Your AWS Account)                     │
│                                                         │
│  EC2 Instance                                           │
│  ├── IAM Role: CostOptimizerEC2Role                    │
│  ├── App: /home/ec2-user/cost_optimizer_ec2            │
│  └── Port: 5001                                        │
└──────────────────────┬──────────────────────────────────┘
                       │ STS AssumeRole (automatic)
                       ↓
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Client A │  │ Client B │  │ Client C │  ... N accounts
│          │  │          │  │          │
│ IAM Role:│  │ IAM Role:│  │ IAM Role:│
│ CostOpti │  │ CostOpti │  │ CostOpti │
│ mizerRO  │  │ mizerRO  │  │ mizerRO  │
└──────────┘  └──────────┘  └──────────┘
```

### How It Works

1. EC2 instance has an IAM Role (`CostOptimizerEC2Role`) attached — no access keys needed
2. App reads client list from `accounts.json`
3. User selects a client from the dropdown in the browser
4. App calls `sts:AssumeRole` into the client's account using temporary credentials
5. Scans all resources (EC2, RDS, EBS, ELB, NAT, S3, etc.) using CloudWatch metrics
6. AI engine generates cost optimization recommendations
7. Results displayed in dashboard with charts, heatmaps, and exportable reports

---

## Prerequisites

- An AWS account to host the application (Tooling Account)
- AWS Console access to both tooling and client accounts
- SSH key pair for EC2 access
- Basic knowledge of AWS IAM and EC2

---

## Step 1: Create IAM Role in Tooling Account

**Account:** Your tooling account (where EC2 will run)

### 1.1 Go to IAM → Roles → Create Role

- **Trusted entity type:** AWS Service
- **Use case:** EC2

### 1.2 Trust Policy

This allows EC2 instances to use this role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 1.3 Permissions Policy

Create an inline policy named `AssumeClientRoles`:

**Option A — Specific accounts (more secure):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": [
        "arn:aws:iam::433222279698:role/CostOptimizerReadOnly",
        "arn:aws:iam::111111111111:role/CostOptimizerReadOnly",
        "arn:aws:iam::222222222222:role/CostOptimizerReadOnly"
      ]
    }
  ]
}
```

**Option B — All accounts with the role (easier to manage):**
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

### 1.4 Role Name

**Name:** `CostOptimizerEC2Role`

### 1.5 Create Instance Profile

After creating the role, it automatically creates an instance profile with the same name. This is what gets attached to EC2.

---

## Step 2: Create IAM Role in Each Client Account

**Repeat this in every client account you want to scan.**

### 2.1 Go to IAM → Roles → Create Role

- **Trusted entity type:** Another AWS Account
- **Account ID:** Enter your tooling account ID

### 2.2 Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<TOOLING_ACCOUNT_ID>:role/CostOptimizerEC2Role"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

> Replace `<TOOLING_ACCOUNT_ID>` with your actual tooling account ID.

### 2.3 Permissions

**Option A — AWS Managed Policy (simple):**
- Attach `ReadOnlyAccess`

**Option B — Custom Minimal Policy (more secure):**
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

> IMPORTANT: Use the same role name in all client accounts for consistency.

---

## Step 3: Launch EC2 Instance

In your **tooling account**, launch an EC2 instance:

| Setting | Value |
|---------|-------|
| **AMI** | Amazon Linux 2023 |
| **Instance type** | t3.small (or t3.micro for testing) |
| **IAM Instance Profile** | `CostOptimizerEC2Role` |
| **Security Group** | Allow inbound TCP port 5001 from your IP/VPN |
| **Key pair** | Create or use existing .pem key |
| **Storage** | 8 GB gp3 (default) |
| **Network** | Public subnet with auto-assign public IP |

### Security Group Rules

| Type | Port | Source | Description |
|------|------|--------|-------------|
| SSH | 22 | Your IP | SSH access |
| Custom TCP | 5001 | Your IP/VPN | App access |

---

## Step 4: Deploy Application on EC2

### 4.1 SSH into EC2

```bash
ssh -i "your-key.pem" ec2-user@<EC2-PUBLIC-IP>
```

### 4.2 Install Dependencies

```bash
sudo yum install python3 python3-pip -y
```

### 4.3 Create App Directory

```bash
mkdir -p /home/ec2-user/cost_optimizer_ec2/static
mkdir -p /home/ec2-user/cost_optimizer_ec2/templates
```

### 4.4 Copy Files from Laptop

From your local machine (Windows CMD):

```cmd
scp -i "your-key.pem" -r D:\cost_optimizer_ec2\* ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/
```

Or copy individual files:

```cmd
scp -i "your-key.pem" D:\cost_optimizer_ec2\app.py ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/
scp -i "your-key.pem" D:\cost_optimizer_ec2\scanner.py ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/
scp -i "your-key.pem" D:\cost_optimizer_ec2\ai_advisor.py ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/
scp -i "your-key.pem" D:\cost_optimizer_ec2\pdf_generator.py ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/
scp -i "your-key.pem" D:\cost_optimizer_ec2\accounts.json ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/
scp -i "your-key.pem" D:\cost_optimizer_ec2\requirements.txt ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/
scp -i "your-key.pem" D:\cost_optimizer_ec2\static\cost_app.js ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/static/
scp -i "your-key.pem" D:\cost_optimizer_ec2\static\cost_style.css ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/static/
scp -i "your-key.pem" D:\cost_optimizer_ec2\templates\index.html ec2-user@<EC2-IP>:/home/ec2-user/cost_optimizer_ec2/templates/
```

### 4.5 Install Python Packages

```bash
cd /home/ec2-user/cost_optimizer_ec2
pip3 install -r requirements.txt
```

### 4.6 Quick Test

```bash
python3 app.py
```

You should see:
```
AWS Cost Optimizer starting at http://0.0.0.0:5001
```

Press `Ctrl+C` to stop after verifying.

---

## Step 5: Create Systemd Service

This makes the app run in background, auto-restart on crash, and start on boot.

```bash
sudo cat << 'EOF' > /etc/systemd/system/cost-optimizer.service
[Unit]
Description=AWS Cost Optimizer Service
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/cost_optimizer_ec2
ExecStart=/usr/bin/python3 /home/ec2-user/cost_optimizer_ec2/app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cost-optimizer
sudo systemctl start cost-optimizer
```

Verify:

```bash
sudo systemctl status cost-optimizer
```

Expected output:
```
● cost-optimizer.service - AWS Cost Optimizer Service
     Active: active (running)
```

---

## Step 6: Add Client Accounts

Edit the accounts file:

```bash
nano /home/ec2-user/cost_optimizer_ec2/accounts.json
```

Format:

```json
[
  {"account_id": "433222279698", "name": "Client A - Production", "role_name": "CostOptimizerReadOnly"},
  {"account_id": "111111111111", "name": "Client B - Staging", "role_name": "CostOptimizerReadOnly"},
  {"account_id": "222222222222", "name": "Client C - Development", "role_name": "CostOptimizerReadOnly"},
  {"account_id": "333333333333", "name": "Client D - DR", "role_name": "CostOptimizerReadOnly"}
]
```

After editing, restart the service:

```bash
sudo systemctl restart cost-optimizer
```

> New accounts appear in the dropdown immediately after restart.

---

## Adding New Client Accounts (Future)

When a new client needs to be onboarded tomorrow or anytime in the future:

### Checklist:

**Step 1:** Create `CostOptimizerReadOnly` role in the new client's AWS account
- Go to IAM -> Roles -> Create Role -> Another AWS Account
- Trust your tooling account ID
- Attach `ReadOnlyAccess` policy
- Role name: `CostOptimizerReadOnly`

**Step 2:** Update the EC2 role permissions (if using specific ARNs)
- Go to your tooling account -> IAM -> Roles -> `CostOptimizerEC2Role`
- Edit the `AssumeClientRoles` policy
- Add the new ARN: `arn:aws:iam::<NEW_ACCOUNT_ID>:role/CostOptimizerReadOnly`
- (Skip this step if you used wildcard `arn:aws:iam::*:role/CostOptimizerReadOnly`)

**Step 3:** SSH into EC2 and edit accounts.json:

```bash
ssh -i your-key.pem ec2-user@<EC2-IP>
nano /home/ec2-user/cost_optimizer_ec2/accounts.json
```

Add the new entry:
```json
{"account_id": "999888777666", "name": "New Client Name", "role_name": "CostOptimizerReadOnly"}
```

> IMPORTANT: Don't forget the comma after the previous entry!

**Step 4:** Restart the service:

```bash
sudo systemctl restart cost-optimizer
```

**Step 5:** Refresh browser — new client appears in dropdown. Done!

### Removing a Client Account:

1. Edit `accounts.json` — remove the entry
2. `sudo systemctl restart cost-optimizer`
3. (Optional) Delete the role from the client's account

---

## Step 7: Access the Application

Open your browser:

```
http://<EC2-PUBLIC-IP>:5001
```

### Usage Flow:

1. Select **AWS Region** from dropdown
2. Select **Client Account** from dropdown (shows names from accounts.json)
3. Click **Connect** — app assumes role into that account
4. Click **Analyze Costs** — scans all resources
5. View dashboard with charts, recommendations, heatmaps
6. Export as **PDF** or **XLSX**

---

## Step 8: Production Hardening (Optional)

### 8.1 HTTPS with ALB

| Step | Action |
|------|--------|
| 1 | Request SSL certificate in ACM (AWS Certificate Manager) |
| 2 | Create Application Load Balancer |
| 3 | Listener: HTTPS 443 → Target Group (EC2:5001) |
| 4 | Update Security Group: remove public 5001, allow only ALB |

### 8.2 Custom Domain

| Step | Action |
|------|--------|
| 1 | Register domain or use existing in Route53 |
| 2 | Create A record → ALB |
| 3 | Access via `https://costoptimizer.yourdomain.com` |

### 8.3 Restrict Access

- Security Group: Allow only your office IP / VPN CIDR
- Or use AWS WAF on ALB for IP whitelisting

### 8.4 Enable AI Recommendations (OpenAI GPT-4o)

Edit the service file:

```bash
sudo nano /etc/systemd/system/cost-optimizer.service
```

Add under `[Service]`:

```ini
Environment=OPENAI_API_KEY=sk-your-api-key-here
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart cost-optimizer
```

### 8.5 Monitoring

- Use CloudWatch Agent for EC2 metrics
- Set alarm on `StatusCheckFailed` to get notified if EC2 goes down

---

## Day-to-Day Operations

| Task | Command |
|------|---------|
| Check app status | `sudo systemctl status cost-optimizer` |
| Restart app | `sudo systemctl restart cost-optimizer` |
| Stop app | `sudo systemctl stop cost-optimizer` |
| View live logs | `journalctl -u cost-optimizer -f` |
| View last 50 log lines | `journalctl -u cost-optimizer -n 50` |
| Add new client | Edit `accounts.json` → `sudo systemctl restart cost-optimizer` |
| Update app code | SCP new files → `sudo systemctl restart cost-optimizer` |
| Check EC2 role works | `curl http://169.254.169.254/latest/meta-data/iam/security-credentials/` |

---

## Automation: Deploy Role to Multiple Accounts

If you manage all accounts under one AWS Organization, use **CloudFormation StackSets** to deploy the `CostOptimizerReadOnly` role to all accounts in one shot.

### CloudFormation Template

Save as `cost-optimizer-role.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Creates CostOptimizerReadOnly role for cross-account scanning

Parameters:
  ToolingAccountId:
    Type: String
    Description: Account ID where the Cost Optimizer EC2 runs

Resources:
  CostOptimizerReadOnlyRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: CostOptimizerReadOnly
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::${ToolingAccountId}:role/CostOptimizerEC2Role'
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/ReadOnlyAccess
```

### Deploy via StackSets

1. Go to **CloudFormation → StackSets → Create StackSet**
2. Upload the template
3. Enter your tooling account ID as parameter
4. Deploy to all target OUs/accounts
5. Done — role created in all accounts automatically

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Unable to locate credentials" | EC2 doesn't have IAM role attached | Attach `CostOptimizerEC2Role` via EC2 → Actions → Security → Modify IAM Role |
| "AssumeRole failed: AccessDenied" | Trust policy in client account doesn't trust your tooling account | Check trust policy in client's `CostOptimizerReadOnly` role |
| "Account not found in accounts.json" | Account not added to config | Edit `accounts.json` and restart |
| App not accessible in browser | Security group blocking port 5001 | Add inbound rule for TCP 5001 |
| App crashes on start | Missing Python packages | Run `pip3 install -r requirements.txt` |
| PDF generation fails | Missing matplotlib/numpy | Run `pip3 install matplotlib numpy` |
| Scan timeout | Too many resources or slow API | Increase `DurationSeconds` in assume_role call |

---

## File Structure on EC2

```
/home/ec2-user/cost_optimizer_ec2/
├── app.py                 # Main Flask application
├── scanner.py             # AWS resource scanner (14 services)
├── ai_advisor.py          # AI recommendation engine
├── pdf_generator.py       # PDF report generator with charts
├── accounts.json          # Client accounts list (edit this)
├── requirements.txt       # Python dependencies
├── Dockerfile             # For containerized deployment
├── static/
│   ├── cost_app.js        # Frontend JavaScript
│   └── cost_style.css     # Frontend styles
└── templates/
    └── index.html         # Dashboard HTML
```

---

## Security Best Practices

1. **Never use access keys** — EC2 instance role provides automatic, rotating credentials
2. **Least privilege** — Client role only has read-only access
3. **Restrict network** — Security group allows only your team's IP
4. **Audit trail** — All AssumeRole calls are logged in CloudTrail
5. **Rotate nothing** — Instance role credentials auto-rotate every few hours
6. **No secrets in code** — accounts.json has no passwords, only account IDs

---

## Contact

For issues or questions, contact the Cloud Operations team.

**Document Version:** 1.0
**Last Updated:** May 2026
**Author:** Orient Technologies — Cloud Operations
