"""
Shared Auth Module — Login, MFA, Session Management
Location on server: /opt/auth/auth.py
"""

import os
import sys
import functools
from io import BytesIO
from datetime import timedelta

import bcrypt
import pyotp
import qrcode
import qrcode.image.svg
from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template, flash, jsonify, current_app
)

sys.path.insert(0, "/opt/auth")
from auth_models import (
    get_user, get_user_by_id, update_user_mfa, update_last_login,
    increment_failed_attempts, is_account_locked, add_audit_log
)

auth_bp = Blueprint("auth", __name__, template_folder="auth_templates")

# Session config
SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT", "30"))


def login_required(f):
    """Decorator to protect routes — requires login + MFA."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        if not session.get("mfa_verified"):
            return redirect(url_for("auth.mfa_verify"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator to protect admin routes."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        if not session.get("mfa_verified"):
            return redirect(url_for("auth.mfa_verify"))
        if session.get("user_role") != "admin":
            return "Access Denied", 403
        return f(*args, **kwargs)
    return decorated


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Username and password are required.", "error")
        return render_template("login.html")

    # Check if account is locked
    if is_account_locked(username):
        flash("Account locked due to too many failed attempts. Try again in 15 minutes.", "error")
        add_audit_log(username, "LOGIN_BLOCKED", "Account locked", request.remote_addr)
        return render_template("login.html")

    user = get_user(username)
    if not user:
        flash("Invalid username or password.", "error")
        return render_template("login.html")

    if not user["is_active"]:
        flash("Account is disabled. Contact admin.", "error")
        return render_template("login.html")

    if not verify_password(password, user["password_hash"]):
        increment_failed_attempts(username)
        add_audit_log(username, "LOGIN_FAILED", "Wrong password", request.remote_addr)
        flash("Invalid username or password.", "error")
        return render_template("login.html")

    # Password correct — set session
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["user_role"] = user["role"]
    session["mfa_verified"] = False

    add_audit_log(username, "PASSWORD_OK", "Password verified", request.remote_addr)

    # Check if MFA is enrolled
    if not user["mfa_enrolled"] or not user["totp_secret"]:
        return redirect(url_for("auth.mfa_setup"))

    return redirect(url_for("auth.mfa_verify"))


@auth_bp.route("/mfa-setup", methods=["GET", "POST"])
def mfa_setup():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    username = session.get("username")
    user = get_user(username)

    # Generate new TOTP secret
    if not user.get("totp_secret"):
        secret = pyotp.random_base32()
        update_user_mfa(username, secret, enrolled=False)
    else:
        secret = user["totp_secret"]

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=username, issuer_name="AWS CloudOps Portal")

    # Generate QR code as base64
    img = qrcode.make(provisioning_uri)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    import base64
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if totp.verify(code, valid_window=1):
            update_user_mfa(username, secret, enrolled=True)
            session["mfa_verified"] = True
            update_last_login(username)
            add_audit_log(username, "MFA_ENROLLED", "MFA setup completed", request.remote_addr)
            next_url = request.args.get("next", "/")
            return redirect(next_url)
        else:
            flash("Invalid code. Try again.", "error")

    return render_template("mfa_setup.html", qr_base64=qr_base64, secret=secret)


@auth_bp.route("/mfa-verify", methods=["GET", "POST"])
def mfa_verify():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        return render_template("mfa.html")

    username = session.get("username")
    user = get_user(username)
    code = request.form.get("code", "").strip()

    if not user or not user["totp_secret"]:
        return redirect(url_for("auth.mfa_setup"))

    totp = pyotp.TOTP(user["totp_secret"])
    if totp.verify(code, valid_window=1):
        session["mfa_verified"] = True
        update_last_login(username)
        add_audit_log(username, "LOGIN_SUCCESS", "MFA verified", request.remote_addr)
        next_url = request.args.get("next", "/")
        return redirect(next_url)
    else:
        increment_failed_attempts(username)
        add_audit_log(username, "MFA_FAILED", "Invalid TOTP code", request.remote_addr)
        flash("Invalid code. Try again.", "error")
        return render_template("mfa.html")


@auth_bp.route("/logout")
def logout():
    username = session.get("username", "unknown")
    add_audit_log(username, "LOGOUT", "", request.remote_addr)
    session.clear()
    return redirect(url_for("auth.login"))
