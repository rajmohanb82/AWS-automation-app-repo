"""
Admin Panel — User Management (port 5002)
Location on server: /root/admin-panel/app.py
"""

import sys
sys.path.insert(0, "/opt/auth")

import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_cors import CORS

from auth import auth_bp, admin_required, hash_password
from auth_models import (
    get_all_users, get_user, create_user, update_password,
    reset_mfa, set_user_active, get_audit_logs, add_audit_log
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-to-random-string-in-production")
app.config["SESSION_COOKIE_NAME"] = "admin_session"
app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 min

CORS(app)
app.register_blueprint(auth_bp)


@app.route("/")
@admin_required
def dashboard():
    users = get_all_users()
    return render_template("dashboard.html", users=users)


@app.route("/create-user", methods=["GET", "POST"])
@admin_required
def create_user_page():
    if request.method == "GET":
        return render_template("create_user.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "viewer")

    if not username or not email or not password:
        flash("All fields are required.", "error")
        return render_template("create_user.html")

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return render_template("create_user.html")

    pw_hash = hash_password(password)
    success = create_user(username, email, pw_hash, role)

    if success:
        add_audit_log(session.get("username"), "USER_CREATED", f"Created user: {username} (role={role})", request.remote_addr)
        flash(f"User '{username}' created successfully.", "success")
        return redirect(url_for("dashboard"))
    else:
        flash(f"Username '{username}' already exists.", "error")
        return render_template("create_user.html")


@app.route("/reset-password/<username>", methods=["POST"])
@admin_required
def reset_password_route(username):
    new_password = request.form.get("new_password", "")
    if len(new_password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("dashboard"))

    user = get_user(username)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("dashboard"))

    pw_hash = hash_password(new_password)
    update_password(username, pw_hash)
    add_audit_log(session.get("username"), "PASSWORD_RESET", f"Reset password for: {username}", request.remote_addr)
    flash(f"Password reset for '{username}'.", "success")
    return redirect(url_for("dashboard"))


@app.route("/reset-mfa/<username>", methods=["POST"])
@admin_required
def reset_mfa_route(username):
    user = get_user(username)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("dashboard"))

    reset_mfa(username)
    add_audit_log(session.get("username"), "MFA_RESET", f"Reset MFA for: {username}", request.remote_addr)
    flash(f"MFA reset for '{username}'. They will re-enroll on next login.", "success")
    return redirect(url_for("dashboard"))


@app.route("/toggle-user/<username>", methods=["POST"])
@admin_required
def toggle_user(username):
    user = get_user(username)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("dashboard"))

    new_state = not user["is_active"]
    set_user_active(username, new_state)
    action = "enabled" if new_state else "disabled"
    add_audit_log(session.get("username"), f"USER_{action.upper()}", f"{action}: {username}", request.remote_addr)
    flash(f"User '{username}' {action}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/audit-log")
@admin_required
def audit_log():
    logs = get_audit_logs(limit=200)
    return render_template("audit_log.html", logs=logs)



@app.route("/auth-validate")
def auth_validate():
    """Used by Nginx auth_request to validate session."""
    if session.get("user_id") and session.get("mfa_verified"):
        return "", 200
    return "", 401

if __name__ == "__main__":
    print("Admin Panel starting at http://0.0.0.0:5002")
    app.run(debug=False, host="0.0.0.0", port=5002)


