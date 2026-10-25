"""
AWS Cost Optimizer — Flask Backend (port 5001)
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

from scanner import scan_all_resources
from ai_advisor import generate_recommendations
from pdf_generator import generate_cost_report

import io

app = Flask(__name__)
CORS(app)

# ─── Auth Config ────────────────────────────────────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "cost-optimizer-change-me-random-string")
app.config["SESSION_COOKIE_NAME"] = "cost_session"
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


TOOLING_PROFILE = os.environ.get("AWS_PROFILE", "CloudOps_Tutorial_Hub")


def get_assume_role_session(account_id, role_name, region):
    """Assume role into a client account and return a boto3 Session."""
    tooling_session = boto3.Session()
    sts = tooling_session.client("sts")
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    resp = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="cost-optimizer",
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
def regions():
    return jsonify({"regions": [
        {"code": "us-east-1",      "name": "US East (N. Virginia)"},
        {"code": "us-east-2",      "name": "US East (Ohio)"},
        {"code": "us-west-1",      "name": "US West (N. California)"},
        {"code": "us-west-2",      "name": "US West (Oregon)"},
        {"code": "ap-south-1",     "name": "Asia Pacific (Mumbai)"},
        {"code": "ap-south-2",     "name": "Asia Pacific (Hyderabad)"},
        {"code": "ap-southeast-1", "name": "Asia Pacific (Singapore)"},
        {"code": "ap-southeast-2", "name": "Asia Pacific (Sydney)"},
        {"code": "ap-northeast-1", "name": "Asia Pacific (Tokyo)"},
        {"code": "eu-west-1",      "name": "Europe (Ireland)"},
        {"code": "eu-west-2",      "name": "Europe (London)"},
        {"code": "eu-central-1",   "name": "Europe (Frankfurt)"},
        {"code": "ca-central-1",   "name": "Canada (Central)"},
    ]})


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
        return jsonify({"error": f"Account '{account_id}' not found in accounts.json"}), 404

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


@app.route("/api/cost-scan", methods=["POST"])
@login_required
def cost_scan():
    """Run full resource scan + AI analysis."""
    data = request.get_json()
    account_id = data.get("account_id")
    region = data.get("region", "ap-south-1")

    if not account_id:
        return jsonify({"error": "account_id required"}), 400

    accounts = load_accounts()
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    try:
        session = get_assume_role_session(account_id, account["role_name"], region)
        session.client("sts").get_caller_identity()
    except Exception as e:
        return jsonify({"error": f"AssumeRole failed: {e}"}), 401

    scan_result = scan_all_resources(session, region)
    ai_result = generate_recommendations(scan_result)

    return jsonify({
        "scan": scan_result,
        "advice": ai_result,
    })


@app.route("/api/generate-cost-report", methods=["POST"])
@login_required
def generate_cost_report_api():
    """Returns a PDF cost optimization report."""
    data = request.get_json()
    scan_data = data.get("scan", {})
    advice_data = data.get("advice", {})
    account_id = data.get("account_id", "unknown")
    region = data.get("region", "ap-south-1")

    accounts = load_accounts()
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    profile_name = account["name"] if account else account_id

    try:
        pdf_bytes = generate_cost_report(scan_data, advice_data, profile_name, region)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"AWS_Cost_Optimization_Report_{profile_name}_{ts}.pdf"
        )
    except Exception as e:
        return jsonify({"error": f"PDF Failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("AWS Cost Optimizer starting at http://127.0.0.1:5001")
    app.run(debug=False, host="0.0.0.0", port=5001)
