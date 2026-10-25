"""AWS access through a local profile or IAM Identity Center."""

import configparser
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import botocore.exceptions

import db

REGIONS = [
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
REGION_CODES = {item["code"] for item in REGIONS}


class AwsLinkError(Exception):
    pass


def list_profiles():
    found = []
    credentials = Path.home() / ".aws" / "credentials"
    config = Path.home() / ".aws" / "config"
    parser = configparser.ConfigParser()
    if credentials.exists():
        parser.read(credentials)
        found.extend(parser.sections())
    parser = configparser.ConfigParser()
    if config.exists():
        parser.read(config)
        for section in parser.sections():
            if section == "default":
                found.append("default")
            elif section.startswith("profile "):
                found.append(section[len("profile ") :])
    unique = []
    for name in found:
        if name not in unique:
            unique.append(name)
    return unique


def _client_error(exc):
    if isinstance(exc, botocore.exceptions.ClientError):
        err = exc.response.get("Error", {})
        code = err.get("Code") or "Error"
        message = err.get("Message") or str(exc)
        return code, message
    return "Error", str(exc)


def connection_status(row=None):
    row = row or db.get_connection()
    expires = row.get("sso_token_expires_at") or ""
    connected = False
    if row.get("mode") == "sso" and row.get("sso_access_token") and expires:
        try:
            connected = datetime.fromisoformat(expires) > db.utcnow()
        except ValueError:
            connected = False
    return {
        "mode": row.get("mode") or "unset",
        "profile_name": row.get("profile_name") or "",
        "sso_start_url": row.get("sso_start_url") or "",
        "sso_region": row.get("sso_region") or "",
        "sso_account_id": row.get("sso_account_id") or "",
        "sso_role_name": row.get("sso_role_name") or "",
        "sso_connected": connected,
    }


def _refresh_sso_token(row):
    if not row.get("sso_refresh_token") or not row.get("sso_client_id"):
        raise AwsLinkError("Sign in to IAM Identity Center again from Settings.")
    client = boto3.client("sso-oidc", region_name=row["sso_region"])
    try:
        token = client.create_token(
            clientId=row["sso_client_id"],
            clientSecret=row["sso_client_secret"],
            grantType="refresh_token",
            refreshToken=row["sso_refresh_token"],
        )
    except botocore.exceptions.ClientError as exc:
        code, message = _client_error(exc)
        raise AwsLinkError(f"IAM Identity Center session expired ({code}). Sign in again. {message}") from exc
    expires = db.iso(db.utcnow() + timedelta(seconds=int(token.get("expiresIn") or 3600)))
    db.save_sso_token(
        row["sso_client_id"],
        row["sso_client_secret"],
        token["accessToken"],
        token.get("refreshToken") or row["sso_refresh_token"],
        expires,
    )
    return token["accessToken"]


def _sso_access_token(row):
    expires = row.get("sso_token_expires_at") or ""
    if row.get("sso_access_token") and expires:
        try:
            if datetime.fromisoformat(expires) > db.utcnow() + timedelta(seconds=60):
                return row["sso_access_token"]
        except ValueError:
            pass
    return _refresh_sso_token(row)


def base_session(region):
    row = db.get_connection()
    mode = row.get("mode") or "unset"
    if mode == "profile":
        profile = row.get("profile_name") or ""
        if not profile:
            raise AwsLinkError("Choose a local AWS profile in Settings.")
        if profile not in list_profiles():
            raise AwsLinkError(f"AWS profile '{profile}' is not on this machine.")
        return boto3.Session(profile_name=profile, region_name=region)
    if mode == "sso":
        for field, label in (
            ("sso_start_url", "start URL"),
            ("sso_region", "SSO region"),
            ("sso_account_id", "SSO account"),
            ("sso_role_name", "permission set"),
        ):
            if not row.get(field):
                raise AwsLinkError(f"IAM Identity Center needs a {label}. Set it in Settings.")
        access_token = _sso_access_token(row)
        sso = boto3.client("sso", region_name=row["sso_region"])
        try:
            creds = sso.get_role_credentials(
                roleName=row["sso_role_name"],
                accountId=row["sso_account_id"],
                accessToken=access_token,
            )["roleCredentials"]
        except botocore.exceptions.ClientError as exc:
            code, message = _client_error(exc)
            raise AwsLinkError(f"Could not get IAM Identity Center credentials ({code}). {message}") from exc
        return boto3.Session(
            aws_access_key_id=creds["accessKeyId"],
            aws_secret_access_key=creds["secretAccessKey"],
            aws_session_token=creds["sessionToken"],
            region_name=region,
        )
    raise AwsLinkError("Choose a local AWS profile or IAM Identity Center in Settings.")


def session_for_account(account, region):
    session = base_session(region)
    role_name = (account.get("role_name") or "").strip()
    target = account["account_id"]
    try:
        caller = session.client("sts").get_caller_identity()["Account"]
    except botocore.exceptions.BotoCoreError as exc:
        raise AwsLinkError(f"AWS credentials could not be loaded. {exc}") from exc
    except botocore.exceptions.ClientError as exc:
        code, message = _client_error(exc)
        raise AwsLinkError(f"AWS credentials were rejected ({code}). {message}") from exc
    if not role_name or caller == target:
        return session
    try:
        assumed = session.client("sts").assume_role(
            RoleArn=f"arn:aws:iam::{target}:role/{role_name}",
            RoleSessionName="ops-console",
            DurationSeconds=3600,
        )["Credentials"]
    except botocore.exceptions.ClientError as exc:
        code, message = _client_error(exc)
        raise AwsLinkError(
            f"Could not assume role {role_name} in account {target} ({code}). {message}"
        ) from exc
    return boto3.Session(
        aws_access_key_id=assumed["AccessKeyId"],
        aws_secret_access_key=assumed["SecretAccessKey"],
        aws_session_token=assumed["SessionToken"],
        region_name=region,
    )


def test_base(region):
    session = base_session(region)
    try:
        identity = session.client("sts").get_caller_identity()
    except botocore.exceptions.ClientError as exc:
        code, message = _client_error(exc)
        raise AwsLinkError(f"Connection test failed ({code}). {message}") from exc
    return {"account": identity["Account"], "arn": identity["Arn"], "region": region}


def test_account(account, region):
    session = session_for_account(account, region)
    identity = session.client("sts").get_caller_identity()
    return {
        "account": identity["Account"],
        "arn": identity["Arn"],
        "region": region,
        "name": account["name"],
    }


def start_sso_device(start_url, sso_region, sso_account_id, sso_role_name):
    if not start_url or not sso_region or not sso_account_id or not sso_role_name:
        raise AwsLinkError("Start URL, SSO region, account ID, and permission set are required.")
    if sso_region not in REGION_CODES:
        raise AwsLinkError("Choose an SSO region from the list.")
    if not sso_account_id.isdigit() or len(sso_account_id) != 12:
        raise AwsLinkError("The Identity Center account ID must be 12 digits.")
    db.save_connection("sso", "", start_url, sso_region, sso_account_id, sso_role_name)
    client = boto3.client("sso-oidc", region_name=sso_region)
    try:
        registered = client.register_client(clientName="ops-console", clientType="public")
        started = client.start_device_authorization(
            clientId=registered["clientId"],
            clientSecret=registered["clientSecret"],
            startUrl=start_url,
        )
    except botocore.exceptions.ClientError as exc:
        code, message = _client_error(exc)
        raise AwsLinkError(f"Could not start IAM Identity Center sign-in ({code}). {message}") from exc
    db.save_sso_pending(
        registered["clientId"],
        registered["clientSecret"],
        started["deviceCode"],
        started.get("interval") or 1,
    )
    return {
        "verification_uri": started.get("verificationUriComplete") or started.get("verificationUri"),
        "user_code": started.get("userCode"),
        "interval": started.get("interval") or 1,
    }


def poll_sso_device():
    row = db.get_connection()
    if not row.get("pending_device_code"):
        raise AwsLinkError("Start IAM Identity Center sign-in first.")
    client = boto3.client("sso-oidc", region_name=row["sso_region"])
    try:
        token = client.create_token(
            clientId=row["pending_client_id"],
            clientSecret=row["pending_client_secret"],
            grantType="urn:ietf:params:oauth:grant-type:device_code",
            deviceCode=row["pending_device_code"],
        )
    except botocore.exceptions.ClientError as exc:
        code, _message = _client_error(exc)
        if code in {"AuthorizationPendingException", "SlowDownException"}:
            return {"status": "pending"}
        if code in {"ExpiredTokenException", "ExpiredToken"}:
            db.clear_sso_pending()
            return {"status": "expired"}
        raise AwsLinkError(f"IAM Identity Center sign-in failed ({code}).") from exc
    expires = db.iso(db.utcnow() + timedelta(seconds=int(token.get("expiresIn") or 3600)))
    db.save_sso_token(
        row["pending_client_id"],
        row["pending_client_secret"],
        token["accessToken"],
        token.get("refreshToken"),
        expires,
    )
    return {"status": "connected"}
