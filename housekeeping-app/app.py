"""
AWS Housekeeping Recommendations — Flask Backend (port 5000)
Uses IAM Role-based AssumeRole for cross-account access.
PATCHED: Auth + MFA protection added.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

import boto3
import botocore.exceptions
from flask import Flask, jsonify, request, render_template, send_file
from flask_cors import CORS

# ─── Auth Integration ───────────────────────────────────────────────────────
sys.path.insert(0, "/opt/auth")
from auth import auth_bp, login_required
# ─────────────────────────────────────────────────────────────────────────────

from checks import run_all_checks
from remediate import dispatch_remediation
from pdf_generator import generate_housekeeping_report
import io

app = Flask(__name__)
CORS(app)

# ─── Auth Config ────────────────────────────────────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "housekeep-change-me-random-string")
app.config["SESSION_COOKIE_NAME"] = "housekeep_session"
app.config["PERMANENT_SESSION_LIFETIME"] = 1800
app.register_blueprint(auth_bp)
# ─────────────────────────────────────────────────────────────────────────────

ACCOUNTS_FILE = Path(__file__).parent / "accounts.json"


# ─── Helpers ────────────────────────────────────────────────────────────────

def load_accounts():
    """Load client accounts from accounts.json."""
    if not ACCOUNTS_FILE.exists():
        return []
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_assume_role_session(account_id, role_name, region):
    """Assume role into a client account and return a boto3 Session."""
    sts = boto3.client("sts")
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    resp = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="housekeep-app",
        DurationSeconds=3600,
    )
    creds = resp["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=region,
    )


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/accounts", methods=["GET"])
@login_required
def get_accounts():
    """Return all client accounts from accounts.json."""
    try:
        accounts = load_accounts()
        return jsonify({"accounts": accounts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/regions", methods=["GET"])
@login_required
def get_regions():
    """Return common AWS regions."""
    regions = [
        {"code": "us-east-1", "name": "US East (N. Virginia)"},
        {"code": "us-east-2", "name": "US East (Ohio)"},
        {"code": "us-west-1", "name": "US West (N. California)"},
        {"code": "us-west-2", "name": "US West (Oregon)"},
        {"code": "ap-south-1", "name": "Asia Pacific (Mumbai)"},
        {"code": "ap-south-2", "name": "Asia Pacific (Hyderabad)"},
        {"code": "ap-southeast-1", "name": "Asia Pacific (Singapore)"},
        {"code": "ap-southeast-2", "name": "Asia Pacific (Sydney)"},
        {"code": "ap-northeast-1", "name": "Asia Pacific (Tokyo)"},
        {"code": "ap-northeast-2", "name": "Asia Pacific (Seoul)"},
        {"code": "eu-west-1", "name": "Europe (Ireland)"},
        {"code": "eu-west-2", "name": "Europe (London)"},
        {"code": "eu-central-1", "name": "Europe (Frankfurt)"},
        {"code": "eu-north-1", "name": "Europe (Stockholm)"},
        {"code": "ca-central-1", "name": "Canada (Central)"},
    ]
    return jsonify({"regions": regions})


@app.route("/api/verify-account", methods=["POST"])
@login_required
def verify_account():
    """Verify that we can assume role into the selected account."""
    data = request.get_json()
    account_id = data.get("account_id")
    region = data.get("region", "ap-south-1")

    if not account_id:
        return jsonify({"error": "account_id required"}), 400

    accounts = load_accounts()
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        return jsonify({"error": f"Account '{account_id}' not found"}), 404

    try:
        session = get_assume_role_session(account_id, account["role_name"], region)
        identity = session.client("sts").get_caller_identity()
        return jsonify({
            "status": "connected",
            "account_id": identity["Account"],
            "arn": identity["Arn"],
            "name": account["name"],
            "region": region,
        })
    except Exception as e:
        return jsonify({"error": f"AssumeRole failed: {str(e)}"}), 401


@app.route("/api/recommendations", methods=["POST"])
@login_required
def recommendations():
    """Run all housekeeping checks for the given account/region."""
    data = request.get_json()
    account_id = data.get("account_id")
    region = data.get("region", "ap-south-1")

    if not account_id:
        return jsonify({"error": "account_id is required"}), 400

    accounts = load_accounts()
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    try:
        session = get_assume_role_session(account_id, account["role_name"], region)
        session.client("sts").get_caller_identity()
    except Exception as e:
        return jsonify({"error": f"Authentication failed: {str(e)}"}), 401

    results = run_all_checks(session, region)
    return jsonify({"results": results})


@app.route("/api/remediate", methods=["POST"])
@login_required
def remediate():
    """Execute automated remediation for a specific finding."""
    data = request.get_json()
    account_id = data.get("account_id")
    region = data.get("region", "ap-south-1")
    finding = data.get("finding", {})

    if not account_id or not finding:
        return jsonify({"error": "account_id and finding are required"}), 400

    accounts = load_accounts()
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    try:
        session = get_assume_role_session(account_id, account["role_name"], region)
        session.client("sts").get_caller_identity()
    except Exception as e:
        return jsonify({"error": f"Authentication failed: {str(e)}"}), 401

    try:
        steps = dispatch_remediation(session, region, finding)
        overall = "success"
        for s in steps:
            if s["status"] == "error":
                overall = "error"
                break
        return jsonify({"steps": steps, "overall": overall})
    except Exception as e:
        return jsonify({"error": str(e), "steps": [{
            "step": 1, "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]}), 500


@app.route("/api/generate-report", methods=["POST"])
@login_required
def generate_report():
    """Generate and return a PDF report."""
    data = request.get_json()
    findings = data.get("findings", [])
    remediations = data.get("remediations", [])
    account_id = data.get("account_id", "unknown")
    region = data.get("region", "ap-south-1")

    accounts = load_accounts()
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    profile_name = account["name"] if account else account_id

    try:
        pdf_bytes = generate_housekeeping_report(findings, remediations, profile_name, region)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"AWS_Housekeeping_Report_{ts}.pdf"
        )
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("AWS Housekeeping UI starting at http://127.0.0.1:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
