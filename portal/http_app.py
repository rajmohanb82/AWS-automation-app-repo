"""Operations console: one app for housekeeping, cost, and governance."""

import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

import advisor
import aws_connect
import charts
import db
import pdf_report
import report_catalog
from aws_connect import REGIONS, REGION_CODES, AwsLinkError
from engine.checks import run_all_checks
from engine.remediate import dispatch_remediation
from engine.scanner import scan_all_resources
from findings import decorate_finding, record_scan

OPEN_PATHS = {
    "/login",
    "/logout",
    "/mfa-setup",
    "/mfa-verify",
    "/auth/oidc/start",
    "/auth/oidc/callback",
    "/api/mobile/bootstrap",
    "/api/mobile/login",
    "/api/mobile/mfa/verify",
    "/api/mobile/mfa/enroll",
    "/api/mobile/logout",
}
ADMIN_PREFIXES = (
    "/settings",
    "/people",
    "/audit",
    "/scope",
    "/api/aws",
    "/api/housekeeping/remediate",
)


class PortalError(Exception):
    pass


def create_app():
    db.init_db()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = db.secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        TEMPLATES_AUTO_RELOAD=True,
    )

    @app.context_processor
    def inject():
        user = _current_user()
        return {
            "csrf": _ensure_csrf(),
            "user": user,
            "org_name": db.get_setting("org_name") or "Operations",
            "mode": db.get_setting("operating_mode") or "msp",
            "cardinality": db.get_setting("product_cardinality") or "single",
            "app_state": _app_state(user),
            "regions": REGIONS,
        }

    @app.before_request
    def guard():
        if request.path == "/favicon.ico":
            return "", 204
        if request.path.startswith("/static/") or request.path == "/healthz":
            return None
        if request.method == "POST":
            rejected = _reject_csrf()
            if rejected:
                return rejected
        if not db.setup_complete():
            if request.path.startswith("/setup") or request.path.startswith("/api/aws/"):
                return None
            return redirect(url_for("setup_mode"))
        if request.path.startswith("/setup"):
            return redirect(url_for("overview"))
        if request.path in OPEN_PATHS:
            return None
        user = _current_user()
        if not user:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Sign in again."}), 401
            return redirect(url_for("login", next=request.path))
        if session.get("auth_method") != "oidc" and not session.get("mfa_verified"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Finish authenticator sign-in before using the console."}), 401
            target = "mfa_verify" if user.get("mfa_enrolled") else "mfa_setup"
            return redirect(url_for(target))
        if request.path.startswith(ADMIN_PREFIXES) and user["role"] != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": "Administrator access is required."}), 403
            return "Administrator access is required.", 403
        return None

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/")
    def overview():
        tree = db.scope_tree()
        user = _current_user()
        scans = _load_scans(24)
        logs = []
        for row in db.get_audit_logs(limit=20):
            if user and user["role"] != "admin" and row["username"] != user["username"]:
                continue
            logs.append(
                {
                    "when": charts.when(row["timestamp"]),
                    "username": row["username"],
                    "action": row["action"],
                    "detail": (row["detail"] or "")[:96],
                }
            )
            if len(logs) >= 8:
                break
        link = aws_connect.connection_status()
        housekeeping_chart, housekeeping_caption = charts.factual_mix(scans, {"housekeeping"})
        governance_chart, governance_caption = charts.factual_mix(scans, {"governance"})
        high_open = 0
        for row in scans:
            if row["kind"] != "housekeeping":
                continue
            counts = row["summary"].get("counts") or {}
            if counts:
                high_open = int(counts.get("HIGH") or 0)
                break
        return render_template(
            "overview.html",
            scans=scans[:8],
            logs=logs,
            housekeeping_chart=housekeeping_chart,
            housekeeping_caption=housekeeping_caption,
            governance_chart=governance_chart,
            governance_caption=governance_caption,
            account_count=len(tree["accounts"]),
            customer_count=len(tree["customers"]),
            product_count=len(tree["products"]),
            high_open=high_open,
            link=link,
        )

    @app.get("/housekeeping")
    def housekeeping_page():
        return render_template("housekeeping.html")

    @app.get("/cost")
    def cost_page():
        return render_template("cost.html")

    @app.get("/governance")
    def governance_page():
        return render_template("governance.html")

    @app.get("/reports")
    def reports_page():
        scans = _load_scans(40)
        groups = report_catalog.catalog_groups()
        for group in groups:
            group["visual"] = charts.topic_visual(group["id"], scans)
        return render_template("reports.html", groups=groups)

    @app.route("/setup", methods=["GET", "POST"])
    def setup_mode():
        if request.method == "POST":
            mode = request.form.get("mode")
            cardinality = request.form.get("cardinality") or "single"
            org_name = (request.form.get("org_name") or "").strip()
            if mode not in {"msp", "product"}:
                flash("Choose MSP or a product company.", "error")
                return redirect(url_for("setup_mode"))
            if len(org_name) < 2 or len(org_name) > 80:
                flash("Enter an organization name.", "error")
                return redirect(url_for("setup_mode"))
            if mode == "product" and cardinality not in {"single", "multiple"}:
                cardinality = "single"
            if mode == "msp":
                cardinality = "none"
            wizard = session.get("wizard") or {}
            wizard.update({"mode": mode, "cardinality": cardinality, "org_name": org_name})
            session["wizard"] = wizard
            return redirect(url_for("setup_admin"))
        wizard = session.get("wizard") or {}
        return render_template("setup.html", step=1, wizard=wizard)

    @app.route("/setup/admin", methods=["GET", "POST"])
    def setup_admin():
        wizard = session.get("wizard") or {}
        if "mode" not in wizard:
            return redirect(url_for("setup_mode"))
        if request.method == "POST":
            username = _clean_username(request.form.get("username"))
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""
            if not username:
                flash("Use 3 to 64 letters, numbers, dots, or hyphens for the username.", "error")
            elif "@" not in email or len(email) > 120:
                flash("Enter a valid email address.", "error")
            elif len(password) < 8:
                flash("Use a password of at least 8 characters.", "error")
            else:
                wizard["username"] = username
                wizard["email"] = email
                wizard["password_hash"] = db.hash_password(password)
                session["wizard"] = wizard
                return redirect(url_for("setup_connection"))
            return redirect(url_for("setup_admin"))
        return render_template("setup.html", step=2, wizard=wizard)

    @app.route("/setup/connection", methods=["GET", "POST"])
    def setup_connection():
        wizard = session.get("wizard") or {}
        if "password_hash" not in wizard:
            return redirect(url_for("setup_admin"))
        if request.method == "POST":
            _save_connection_form()
            return redirect(url_for("setup_scope"))
        return render_template(
            "setup.html",
            step=3,
            wizard=wizard,
            profiles=aws_connect.list_profiles(),
            link=aws_connect.connection_status(),
        )

    @app.route("/setup/scope", methods=["GET", "POST"])
    def setup_scope():
        wizard = session.get("wizard") or {}
        if "username" not in wizard:
            return redirect(url_for("setup_admin"))
        if request.method == "POST":
            if request.form.get("skip") != "1":
                error = _create_initial_scope(wizard)
                if error:
                    flash(error, "error")
                    return redirect(url_for("setup_scope"))
            return _finish_setup(wizard)
        return render_template("setup.html", step=4, wizard=wizard)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if _fully_signed_in():
            return redirect(url_for("overview"))
        oidc = db.get_oidc()
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            if db.is_account_locked(username):
                flash("This account is locked for 15 minutes after repeated failures.", "error")
                db.add_audit(username, "LOGIN_BLOCKED", "Account locked", request.remote_addr)
                return _render_auth("password", oidc=oidc, username=username)
            user = db.get_user(username)
            if not user or not user["password_hash"] or not db.verify_password(password, user["password_hash"]):
                if user and not user["password_hash"]:
                    flash("This account signs in with the identity provider.", "error")
                else:
                    if user:
                        db.increment_failed_attempts(username)
                        db.add_audit(username, "LOGIN_FAILED", "Wrong password", request.remote_addr)
                    flash("The username or password is incorrect.", "error")
                return _render_auth("password", oidc=oidc, username=username)
            if not user["is_active"]:
                flash("This account is disabled. Ask an administrator to enable it.", "error")
                return _render_auth("password", oidc=oidc, username=username)
            _start_session(user, "local")
            db.add_audit(username, "PASSWORD_OK", "Password verified", request.remote_addr)
            return redirect(url_for("mfa_verify" if user["mfa_enrolled"] else "mfa_setup"))
        return _render_auth("password", oidc=oidc)

    @app.route("/mfa-setup", methods=["GET", "POST"])
    def mfa_setup():
        user = _current_user()
        if not user or session.get("auth_method") == "oidc":
            return redirect(url_for("login"))
        import pyotp
        import qrcode
        import qrcode.image.svg

        secret = user.get("totp_secret")
        if not secret:
            secret = pyotp.random_base32()
            db.update_user_mfa(user["username"], secret, False)
            user = db.get_user(user["username"])
            secret = user["totp_secret"]
        totp = pyotp.TOTP(secret)
        issuer = db.get_setting("org_name") or "Operations console"
        uri = totp.provisioning_uri(name=user["username"], issuer_name=issuer)
        image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathFillImage)
        svg = image.to_string().decode("utf-8")
        pin = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))
        if request.method == "POST":
            db.update_user_mfa(user["username"], secret, True)
            session["mfa_verified"] = True
            db.update_last_login(user["username"])
            db.add_audit(user["username"], "MFA_ENROLLED", "Authenticator enrolled from QR", request.remote_addr)
            return redirect(_safe_next(request.args.get("next")))
        return _render_auth("enroll", svg=svg, pin=pin)

    @app.route("/mfa-verify", methods=["GET", "POST"])
    def mfa_verify():
        user = _current_user()
        if not user or session.get("auth_method") == "oidc":
            return redirect(url_for("login"))
        if not user.get("totp_secret") or not user.get("mfa_enrolled"):
            return redirect(url_for("mfa_setup"))
        if request.method == "POST":
            import pyotp

            code = (request.form.get("code") or "").strip().replace(" ", "")
            if pyotp.TOTP(user["totp_secret"]).verify(code, valid_window=1):
                session["mfa_verified"] = True
                db.update_last_login(user["username"])
                db.add_audit(user["username"], "LOGIN_SUCCESS", "MFA verified", request.remote_addr)
                return redirect(_safe_next(request.args.get("next")))
            db.increment_failed_attempts(user["username"])
            db.add_audit(user["username"], "MFA_FAILED", "Invalid authenticator code", request.remote_addr)
            flash("That code was not accepted.", "error")
        return _render_auth("verify")

    @app.post("/logout")
    def logout():
        username = session.get("username", "")
        if username:
            db.add_audit(username, "LOGOUT", "", request.remote_addr or "")
        session.clear()
        return redirect(url_for("login"))

    @app.get("/auth/oidc/start")
    def oidc_start():
        client = _oidc_client(app)
        if client is None:
            flash("Identity provider sign-in is not configured.", "error")
            return redirect(url_for("login"))
        try:
            return client.authorize_redirect(url_for("oidc_callback", _external=True))
        except Exception as exc:
            flash(f"The identity provider could not be contacted. {exc}", "error")
            return redirect(url_for("login"))

    @app.get("/auth/oidc/callback")
    def oidc_callback():
        client = _oidc_client(app)
        cfg = db.get_oidc()
        if client is None or not cfg or not cfg["enabled"]:
            return redirect(url_for("login"))
        try:
            token = client.authorize_access_token()
            userinfo = token.get("userinfo") or client.userinfo()
        except Exception as exc:
            flash(f"Identity provider sign-in did not complete. {exc}", "error")
            return redirect(url_for("login"))
        sub = str(userinfo.get("sub") or "")
        email = (userinfo.get("email") or "").strip()
        if not sub or not email:
            flash("The identity provider must release the email and profile claims.", "error")
            return redirect(url_for("login"))
        groups = _claim_groups(userinfo)
        existing = db.get_user_by_oidc(sub)
        role = _role_from_groups(groups, cfg, existing)
        if existing:
            if not existing["is_active"]:
                flash("This account is disabled.", "error")
                return redirect(url_for("login"))
            if role != existing["role"]:
                db.set_user_role(existing["username"], role)
                existing = db.get_user(existing["username"])
            _start_session(existing, "oidc")
            db.update_last_login(existing["username"])
            db.add_audit(existing["username"], "LOGIN_SUCCESS", "OIDC", request.remote_addr)
            return redirect(url_for("overview"))
        preferred = userinfo.get("preferred_username") or email.split("@")[0]
        username = _unique_username(preferred)
        created = db.create_user(username, email, None, role=role, oidc_sub=sub)
        if not created:
            flash("An account with that identity already exists.", "error")
            return redirect(url_for("login"))
        user = db.get_user_by_id(created)
        _start_session(user, "oidc")
        db.update_last_login(username)
        db.add_audit(username, "LOGIN_SUCCESS", "OIDC enrollment", request.remote_addr)
        return redirect(url_for("overview"))

    @app.route("/settings", methods=["GET"])
    def settings():
        return render_template(
            "settings.html",
            profiles=aws_connect.list_profiles(),
            link=aws_connect.connection_status(),
            oidc=db.get_oidc(),
            redirect_uri=url_for("oidc_callback", _external=True),
        )

    @app.post("/settings/model")
    def settings_model():
        mode = request.form.get("mode")
        cardinality = request.form.get("cardinality") or "single"
        if mode not in {"msp", "product"}:
            flash("Choose MSP or a product company.", "error")
            return redirect(url_for("settings"))
        if mode == "msp":
            cardinality = "none"
        elif cardinality not in {"single", "multiple"}:
            cardinality = "single"
        db.set_setting("operating_mode", mode)
        db.set_setting("product_cardinality", cardinality)
        db.add_audit(session.get("username"), "MODEL_CHANGED", f"{mode}/{cardinality}", request.remote_addr)
        flash("Operating model saved. Existing accounts stay in the database.", "success")
        return redirect(url_for("settings"))

    @app.post("/settings/oidc")
    def settings_oidc():
        enabled = request.form.get("enabled") == "1"
        issuer = (request.form.get("issuer") or "").strip().rstrip("/")
        client_id = (request.form.get("client_id") or "").strip()
        secret = request.form.get("client_secret") or ""
        scopes = (request.form.get("scopes") or "openid email profile").strip()
        label = (request.form.get("label") or "Identity provider").strip()
        admin_group = (request.form.get("admin_group") or "").strip()
        if enabled and (not issuer.startswith("https://") or not client_id):
            flash("An enabled identity provider needs an https issuer and a client id.", "error")
            return redirect(url_for("settings"))
        if enabled and not secret and not (db.get_oidc() or {}).get("client_secret"):
            flash("Enter the client secret the first time you enable the provider.", "error")
            return redirect(url_for("settings"))
        db.save_oidc(
            enabled,
            issuer,
            client_id,
            secret,
            url_for("oidc_callback", _external=True),
            scopes,
            label,
            admin_group,
        )
        db.add_audit(session.get("username"), "OIDC_SAVED", issuer, request.remote_addr)
        flash("Identity provider settings saved.", "success")
        return redirect(url_for("settings"))

    @app.post("/settings/aws")
    def settings_aws():
        _save_connection_form()
        db.add_audit(session.get("username"), "AWS_CONNECTION_SAVED", request.form.get("mode") or "", request.remote_addr)
        flash("AWS connection saved.", "success")
        return redirect(url_for("settings"))

    @app.get("/people")
    def people():
        return render_template("people.html", people=db.get_all_users())

    @app.post("/people/create")
    def people_create():
        username = _clean_username(request.form.get("username"))
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        role = request.form.get("role") if request.form.get("role") in {"admin", "viewer"} else "viewer"
        if not username or "@" not in email or len(password) < 8:
            flash("Enter a username, email, and a password of at least 8 characters.", "error")
            return redirect(url_for("people"))
        if not db.create_user(username, email, db.hash_password(password), role):
            flash("That username already exists.", "error")
            return redirect(url_for("people"))
        db.add_audit(session.get("username"), "USER_CREATED", username, request.remote_addr)
        flash(f"{username} can sign in and will enroll an authenticator on first login.", "success")
        return redirect(url_for("people"))

    @app.post("/people/<username>/password")
    def people_password(username):
        user = _named_user(username)
        if not user:
            return redirect(url_for("people"))
        password = request.form.get("password") or ""
        if len(password) < 8:
            flash("Use a password of at least 8 characters.", "error")
            return redirect(url_for("people"))
        if not user["password_hash"]:
            flash("This person signs in with the identity provider.", "error")
            return redirect(url_for("people"))
        db.update_password(username, db.hash_password(password))
        db.add_audit(session.get("username"), "PASSWORD_RESET", username, request.remote_addr)
        flash(f"Password updated for {username}.", "success")
        return redirect(url_for("people"))

    @app.post("/people/<username>/role")
    def people_role(username):
        user = _named_user(username)
        role = request.form.get("role")
        if not user or role not in {"admin", "viewer"}:
            return redirect(url_for("people"))
        if user["role"] == "admin" and role != "admin" and db.count_active_admins(exclude_id=user["id"]) == 0:
            flash("Keep at least one active administrator.", "error")
            return redirect(url_for("people"))
        db.set_user_role(username, role)
        if session.get("username") == username:
            session["user_role"] = role
        db.add_audit(session.get("username"), "ROLE_CHANGED", f"{username}={role}", request.remote_addr)
        flash(f"{username} is now {role}.", "success")
        return redirect(url_for("people"))

    @app.post("/people/<username>/active")
    def people_active(username):
        user = _named_user(username)
        if not user:
            return redirect(url_for("people"))
        if user["id"] == session.get("user_id"):
            flash("Ask another administrator to disable your account.", "error")
            return redirect(url_for("people"))
        new_state = not user["is_active"]
        if user["role"] == "admin" and not new_state and db.count_active_admins(exclude_id=user["id"]) == 0:
            flash("Keep at least one active administrator.", "error")
            return redirect(url_for("people"))
        db.set_user_active(username, new_state)
        action = "enabled" if new_state else "disabled"
        db.add_audit(session.get("username"), "USER_STATE", f"{username} {action}", request.remote_addr)
        flash(f"{username} is {action}.", "success")
        return redirect(url_for("people"))

    @app.post("/people/<username>/mfa-reset")
    def people_mfa(username):
        user = _named_user(username)
        if not user:
            return redirect(url_for("people"))
        if not user["password_hash"]:
            flash("Identity provider accounts use the provider's own verification.", "error")
            return redirect(url_for("people"))
        db.reset_mfa(username)
        db.add_audit(session.get("username"), "MFA_RESET", username, request.remote_addr)
        flash(f"{username} will enroll an authenticator at the next sign-in.", "success")
        return redirect(url_for("people"))

    @app.get("/audit")
    def audit():
        events = []
        for row in db.recent_events():
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                payload = {}
            events.append({**row, "payload": payload})
        return render_template("audit.html", logs=db.get_audit_logs(), events=events)

    @app.get("/scope")
    def scope_page():
        return render_template("scope.html", tree=db.scope_tree())

    @app.post("/scope/customers")
    def scope_customer():
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Enter a customer name.", "error")
        else:
            db.create_customer(name)
            flash(f"Customer {name} added.", "success")
        return redirect(url_for("scope_page"))

    @app.post("/scope/products")
    def scope_product():
        if db.get_setting("product_cardinality") == "single" and db.list_products():
            flash("This installation is set to a single product. Add environments under that product.", "error")
            return redirect(url_for("scope_page"))
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Enter a product name.", "error")
        else:
            db.create_product(name)
            flash(f"Product {name} added.", "success")
        return redirect(url_for("scope_page"))

    @app.post("/scope/environments")
    def scope_environment():
        product_id = _maybe_int(request.form.get("product_id"))
        name = (request.form.get("name") or "").strip()
        if not product_id or not name or not _product_exists(product_id):
            flash("Choose a product and name the environment.", "error")
        else:
            db.create_environment(product_id, name)
            flash(f"Environment {name} added.", "success")
        return redirect(url_for("scope_page"))

    @app.post("/scope/accounts")
    def scope_account():
        error = _create_account_from_form()
        flash(error or "Account added.", "error" if error else "success")
        return redirect(url_for("scope_page"))

    @app.post("/scope/delete")
    def scope_delete():
        table = request.form.get("table")
        row_id = _maybe_int(request.form.get("id"))
        if table not in {"customers", "products", "environments", "accounts"} or not row_id:
            abort(400)
        db.delete_row(table, row_id)
        db.add_audit(session.get("username"), "SCOPE_DELETED", f"{table}:{row_id}", request.remote_addr)
        flash("Removed.", "success")
        return redirect(url_for("scope_page"))

    @app.post("/api/selection")
    def api_selection():
        data = request.get_json(silent=True) or {}
        region = data.get("region") if data.get("region") in REGION_CODES else "us-east-1"
        session["selection"] = {
            "customer_id": _maybe_int(data.get("customer_id")),
            "product_id": _maybe_int(data.get("product_id")),
            "environment_id": _maybe_int(data.get("environment_id")),
            "account_pk": _maybe_int(data.get("account_pk")),
            "region": region,
        }
        session.modified = True
        return jsonify({"ok": True})

    @app.post("/api/aws/test")
    def api_aws_test():
        data = request.get_json(silent=True) or {}
        if data.get("mode") in {"profile", "sso"}:
            sso_region = data.get("sso_region") if data.get("sso_region") in REGION_CODES else "us-east-1"
            db.save_connection(
                data["mode"],
                data.get("profile_name") or "",
                data.get("sso_start_url") or "",
                sso_region,
                data.get("sso_account_id") or "",
                data.get("sso_role_name") or "",
            )
        region = data.get("region") if data.get("region") in REGION_CODES else "us-east-1"
        try:
            account_pk = _maybe_int(data.get("account_pk"))
            if account_pk:
                account = db.get_account(account_pk)
                if not account:
                    raise AwsLinkError("Choose an account.")
                result = aws_connect.test_account(account, region)
            else:
                result = aws_connect.test_base(region)
        except AwsLinkError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "connected", **result})

    @app.post("/api/aws/sso/start")
    def api_sso_start():
        data = request.get_json(silent=True) or {}
        try:
            result = aws_connect.start_sso_device(
                (data.get("sso_start_url") or "").strip(),
                (data.get("sso_region") or "").strip(),
                (data.get("sso_account_id") or "").strip(),
                (data.get("sso_role_name") or "").strip(),
            )
        except AwsLinkError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    @app.post("/api/aws/sso/poll")
    def api_sso_poll():
        try:
            return jsonify(aws_connect.poll_sso_device())
        except AwsLinkError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/housekeeping/scan")
    def api_housekeeping_scan():
        try:
            account, region, aws = _open_account()
            findings = [
                decorate_finding(item, account["account_id"], region)
                for item in run_all_checks(aws, region)
            ]
            summary = record_scan("housekeeping", account, region, session.get("username"), findings)
        except (AwsLinkError, PortalError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("housekeeping scan failed")
            return jsonify({"error": str(exc)}), 500
        return jsonify({"findings": findings, "summary": summary})

    @app.post("/api/housekeeping/remediate")
    def api_remediate():
        data = request.get_json(silent=True) or {}
        finding = data.get("finding") or {}
        if not finding.get("resource_id") or not finding.get("title"):
            return jsonify({"error": "A finding with a resource id is required."}), 400
        try:
            account, region, aws = _open_account()
            steps = dispatch_remediation(aws, region, finding)
        except (AwsLinkError, PortalError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("remediation failed")
            return jsonify({"error": str(exc)}), 500
        overall = "error" if any(step.get("status") == "error" for step in steps) else "success"
        if all(step.get("status") == "skipped" for step in steps):
            overall = "skipped"
        db.add_event(
            "remediation.completed",
            json.dumps(
                {
                    "finding_id": finding.get("finding_id"),
                    "account_id": account["account_id"],
                    "region": region,
                    "title": finding.get("title"),
                    "resource_id": finding.get("resource_id"),
                    "overall": overall,
                    "actor": session.get("username"),
                }
            ),
        )
        db.add_audit(
            session.get("username"),
            "REMEDIATE",
            f"{account['account_id']} {finding.get('resource_id')} {overall}",
            request.remote_addr,
        )
        return jsonify({"steps": steps, "overall": overall})

    @app.post("/api/housekeeping/pdf")
    def api_housekeeping_pdf():
        data = request.get_json(silent=True) or {}
        findings = data.get("findings") or []
        if not isinstance(findings, list):
            return jsonify({"error": "Findings are required."}), 400
        name = (data.get("account_name") or "account")[:80]
        region = data.get("region") or ""
        payload = pdf_report.housekeeping_pdf(name, region, findings[:800])
        return send_file(
            BytesIO(payload),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="housekeeping-report.pdf",
        )

    @app.post("/api/cost/recommendations")
    def api_cost_native():
        try:
            account, region, aws = _open_account()
            result = advisor.native_recommendations(aws, region)
            summary = record_scan(
                "cost", account, region, session.get("username"), result["recommendations"]
            )
        except (AwsLinkError, PortalError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("cost recommendations failed")
            return jsonify({"error": str(exc)}), 500
        result["summary"] = summary
        return jsonify(result)

    @app.post("/api/cost/inventory")
    def api_cost_inventory():
        try:
            account, region, aws = _open_account()
            scan = scan_all_resources(aws, region)
            recommendations = advisor.rules_from_scan(scan, account["account_id"], region)
            summary = record_scan("cost-inventory", account, region, session.get("username"), recommendations)
        except (AwsLinkError, PortalError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("inventory failed")
            return jsonify({"error": str(exc)}), 500
        return jsonify(
            {
                "recommendations": recommendations,
                "summary": summary,
                "total_cost": scan.get("total_cost"),
                "actual_30d_ce_cost": scan.get("actual_30d_ce_cost"),
                "total_saving": scan.get("total_saving"),
                "optimization_score": scan.get("optimization_score"),
                "service_summary": scan.get("summary"),
                "errors": scan.get("errors") or [],
                "notes": [
                    "Inventory estimates use published on-demand prices and CloudWatch. "
                    "Cost Optimization Hub is the figure that includes this account's discounts."
                ],
                "source": "Documented rules",
            }
        )

    @app.post("/api/cost/pdf")
    def api_cost_pdf():
        data = request.get_json(silent=True) or {}
        rows = data.get("recommendations") or []
        if not isinstance(rows, list):
            return jsonify({"error": "Recommendations are required."}), 400
        payload = pdf_report.cost_pdf(
            (data.get("account_name") or "account")[:80],
            data.get("region") or "",
            rows[:800],
            data.get("notes") or [],
        )
        return send_file(
            BytesIO(payload),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="cost-report.pdf",
        )

    @app.post("/api/governance/scan")
    def api_governance():
        try:
            account, region, aws = _open_account()
            findings = [
                decorate_finding(item, account["account_id"], region)
                for item in run_all_checks(aws, region)
            ]
            pillars = {name: 0 for name in (
                "Security",
                "Reliability",
                "Cost optimization",
                "Operational excellence",
                "Performance",
            )}
            for finding in findings:
                pillars[finding["pillar"]] = pillars.get(finding["pillar"], 0) + 1
            trusted = advisor.trusted_advisor(aws)
            summary = record_scan("governance", account, region, session.get("username"), findings)
        except (AwsLinkError, PortalError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("governance scan failed")
            return jsonify({"error": str(exc)}), 500
        return jsonify(
            {"findings": findings, "pillars": pillars, "trusted_advisor": trusted, "summary": summary}
        )

    @app.post("/api/reports/<report_id>")
    def api_report(report_id):
        spec = report_catalog.get_report(report_id)
        if not spec:
            return jsonify({"error": "That report is not in the library."}), 404
        try:
            account, region, aws = _open_account()
            ctx = _collect_report(spec, account, region, aws)
            document = report_catalog.build_document(spec, ctx)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            document["subtitle"] = f"{account['name']} ({account['account_id']})   |   {region}   |   {stamp}"
            payload = pdf_report.render_document(
                document,
                org=db.get_setting("org_name") or "Operations",
            )
        except (AwsLinkError, PortalError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("report failed")
            return jsonify({"error": str(exc)}), 500
        db.add_audit(
            session.get("username"),
            "REPORT",
            f"{report_id} {account['account_id']} {region}",
            request.remote_addr,
        )
        slug = re.sub(r"[^a-z0-9]+", "-", spec["title"].lower()).strip("-")
        return send_file(
            BytesIO(payload),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{spec['domain']}-{slug}.pdf",
        )

    @app.get("/api/mobile/bootstrap")
    def mobile_bootstrap():
        return jsonify({
            "csrf": _ensure_csrf(),
            "app": "CloudSync",
            "company": "Vayu Technologies",
            "org_name": db.get_setting("org_name") or "Operations",
        })

    @app.post("/api/mobile/login")
    def mobile_login():
        body = request.get_json(silent=True) or {}
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        if db.is_account_locked(username):
            db.add_audit(username, "LOGIN_BLOCKED", "Account locked", request.remote_addr)
            return jsonify({"error": "This account is locked for 15 minutes after repeated failures."}), 401
        user = db.get_user(username)
        if not user or not user["password_hash"] or not db.verify_password(password, user["password_hash"]):
            if user and user["password_hash"]:
                db.increment_failed_attempts(username)
                db.add_audit(username, "LOGIN_FAILED", "Wrong password", request.remote_addr)
            message = (
                "This account signs in with the identity provider."
                if user and not user["password_hash"]
                else "The username or password is incorrect."
            )
            return jsonify({"error": message}), 401
        if not user["is_active"]:
            return jsonify({"error": "This account is disabled. Ask an administrator to enable it."}), 401
        _start_session(user, "local")
        db.add_audit(username, "PASSWORD_OK", "Password verified", request.remote_addr)
        return jsonify({
            "step": "verify" if user["mfa_enrolled"] else "enroll",
            "username": user["username"],
            "csrf": session.get("csrf"),
        })

    @app.post("/api/mobile/mfa/verify")
    def mobile_mfa_verify():
        user = _current_user()
        if not user or session.get("auth_method") == "oidc":
            return jsonify({"error": "Sign in again."}), 401
        if not user.get("totp_secret") or not user.get("mfa_enrolled"):
            return jsonify({"error": "Register an authenticator first.", "step": "enroll"}), 409
        import pyotp

        body = request.get_json(silent=True) or {}
        code = (body.get("code") or "").strip().replace(" ", "")
        if not pyotp.TOTP(user["totp_secret"]).verify(code, valid_window=1):
            db.increment_failed_attempts(user["username"])
            db.add_audit(user["username"], "MFA_FAILED", "Invalid authenticator code", request.remote_addr)
            return jsonify({"error": "That code was not accepted."}), 401
        session["mfa_verified"] = True
        db.update_last_login(user["username"])
        db.add_audit(user["username"], "LOGIN_SUCCESS", "MFA verified", request.remote_addr)
        return jsonify({"ok": True, "csrf": session.get("csrf")})

    @app.route("/api/mobile/mfa/enroll", methods=["GET", "POST"])
    def mobile_mfa_enroll():
        user = _current_user()
        if not user or session.get("auth_method") == "oidc":
            return jsonify({"error": "Sign in again."}), 401
        import pyotp

        secret = user.get("totp_secret")
        if not secret:
            secret = pyotp.random_base32()
            db.update_user_mfa(user["username"], secret, False)
            user = db.get_user(user["username"])
            secret = user["totp_secret"]
        if request.method == "POST":
            db.update_user_mfa(user["username"], secret, True)
            session["mfa_verified"] = True
            db.update_last_login(user["username"])
            db.add_audit(user["username"], "MFA_ENROLLED", "Authenticator enrolled from the Android app", request.remote_addr)
            return jsonify({"ok": True, "csrf": session.get("csrf")})
        issuer = db.get_setting("org_name") or "CloudSync"
        uri = pyotp.TOTP(secret).provisioning_uri(name=user["username"], issuer_name=issuer)
        pin = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))
        return jsonify({"username": user["username"], "pin": pin, "uri": uri, "csrf": session.get("csrf")})

    @app.post("/api/mobile/logout")
    def mobile_logout():
        username = session.get("username", "")
        if username:
            db.add_audit(username, "LOGOUT", "", request.remote_addr or "")
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/mobile/home")
    def mobile_home():
        tree = db.scope_tree()
        user = _current_user()
        scans = _load_scans(24)
        logs = []
        for row in db.get_audit_logs(limit=20):
            if user and user["role"] != "admin" and row["username"] != user["username"]:
                continue
            logs.append({
                "when": charts.when(row["timestamp"]),
                "username": row["username"],
                "action": row["action"],
                "detail": (row["detail"] or "")[:96],
            })
            if len(logs) >= 8:
                break
        link = aws_connect.connection_status()
        aws_label = {"profile": "Profile", "sso": "Identity Center"}.get(link.get("mode"), "Not set")
        high_open = 0
        for row in scans:
            if row["kind"] != "housekeeping":
                continue
            counts = (row.get("summary") or {}).get("counts") or {}
            if counts:
                high_open = int(counts.get("HIGH") or 0)
                break

        def pack(kinds):
            series, caption = charts.factual_points(scans, kinds)
            return {
                "caption": caption,
                "series": [
                    {"label": item["label"], "value": item["value"], "tone": item["tone"]}
                    for item in series
                ],
            }

        groups = []
        for group in report_catalog.catalog_groups():
            groups.append({
                "id": group["id"],
                "label": group["label"],
                "headline": group["headline"],
                "blurb": group["blurb"],
                "reports": [
                    {
                        "id": item["id"],
                        "code": item["code"],
                        "title": item["title"],
                        "audience": item["audience"],
                        "summary": item["summary"],
                    }
                    for item in group["reports"]
                ],
            })
        return jsonify({
            "user": {"username": user["username"], "role": user["role"]},
            "org_name": db.get_setting("org_name") or "Operations",
            "mode": db.get_setting("operating_mode") or "product",
            "account_count": len(tree["accounts"]),
            "product_count": len(tree["products"]),
            "customer_count": len(tree["customers"]),
            "aws": aws_label,
            "high_open": high_open,
            "housekeeping": pack({"housekeeping"}),
            "governance": pack({"governance"}),
            "cost": pack({"cost", "cost-inventory"}),
            "scans": [_scan_brief(row) for row in scans[:8]],
            "logs": logs,
            "accounts": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "account_id": item["account_id"],
                    "region": item["default_region"],
                }
                for item in tree["accounts"]
            ],
            "reports": groups,
        })

    @app.post("/api/mobile/reports/<report_id>")
    def mobile_report(report_id):
        spec = report_catalog.get_report(report_id)
        if not spec:
            return jsonify({"error": "That report is not in the library."}), 404
        try:
            account, region, aws = _open_account()
            ctx = _collect_report(spec, account, region, aws)
            document = report_catalog.build_document(spec, ctx)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            document["subtitle"] = f"{account['name']} ({account['account_id']})   |   {region}   |   {stamp}"
            payload = _mobile_document(document)
        except (AwsLinkError, PortalError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("mobile report failed")
            return jsonify({"error": str(exc)}), 500
        db.add_audit(
            session.get("username"),
            "REPORT",
            f"{report_id} {account['account_id']} {region}",
            request.remote_addr,
        )
        return jsonify(payload)

    @app.post("/api/mobile/reports/<report_id>/pdf")
    def mobile_report_pdf(report_id):
        spec = report_catalog.get_report(report_id)
        if not spec:
            return jsonify({"error": "That report is not in the library."}), 404
        try:
            account, region, aws = _open_account()
            ctx = _collect_report(spec, account, region, aws)
            document = report_catalog.build_document(spec, ctx)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            document["subtitle"] = f"{account['name']} ({account['account_id']})   |   {region}   |   {stamp}"
            payload = pdf_report.render_document(
                document,
                org=db.get_setting("org_name") or "Operations",
            )
        except (AwsLinkError, PortalError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("mobile report pdf failed")
            return jsonify({"error": str(exc)}), 500
        db.add_audit(
            session.get("username"),
            "REPORT",
            f"{report_id} pdf {account['account_id']} {region}",
            request.remote_addr,
        )
        slug = re.sub(r"[^a-z0-9]+", "-", spec["title"].lower()).strip("-")
        return send_file(
            BytesIO(payload),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{spec['domain']}-{slug}.pdf",
        )

    @app.get("/api/mobile/settings")
    def mobile_settings():
        denied = _admin_json()
        if denied:
            return denied
        link = aws_connect.connection_status()
        return jsonify({
            "mode": db.get_setting("operating_mode") or "msp",
            "cardinality": db.get_setting("product_cardinality") or "single",
            "connection": link,
            "profiles": aws_connect.list_profiles(),
            "regions": REGIONS,
        })

    @app.post("/api/mobile/settings/aws")
    def mobile_settings_aws():
        denied = _admin_json()
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        mode = body.get("mode") or "unset"
        if mode not in {"profile", "sso", "unset"}:
            mode = "unset"
        sso_region = body.get("sso_region") or "us-east-1"
        if sso_region not in REGION_CODES:
            sso_region = "us-east-1"
        db.save_connection(
            mode,
            body.get("profile_name") or "",
            body.get("sso_start_url") or "",
            sso_region,
            body.get("sso_account_id") or "",
            body.get("sso_role_name") or "",
        )
        db.add_audit(session.get("username"), "AWS_CONNECTION_SAVED", mode, request.remote_addr)
        return jsonify({"ok": True, "connection": aws_connect.connection_status()})

    @app.post("/api/mobile/aws/test")
    def mobile_aws_test():
        denied = _admin_json()
        if denied:
            return denied
        data = request.get_json(silent=True) or {}
        if data.get("mode") in {"profile", "sso"}:
            sso_region = data.get("sso_region") if data.get("sso_region") in REGION_CODES else "us-east-1"
            db.save_connection(
                data["mode"],
                data.get("profile_name") or "",
                data.get("sso_start_url") or "",
                sso_region,
                data.get("sso_account_id") or "",
                data.get("sso_role_name") or "",
            )
        region = data.get("region") if data.get("region") in REGION_CODES else "us-east-1"
        try:
            account_pk = _maybe_int(data.get("account_pk"))
            if account_pk:
                account = db.get_account(account_pk)
                if not account:
                    raise AwsLinkError("Choose an account.")
                result = aws_connect.test_account(account, region)
            else:
                result = aws_connect.test_base(region)
        except AwsLinkError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "connected", **result})

    @app.post("/api/mobile/aws/sso/start")
    def mobile_sso_start():
        denied = _admin_json()
        if denied:
            return denied
        data = request.get_json(silent=True) or {}
        try:
            result = aws_connect.start_sso_device(
                (data.get("sso_start_url") or "").strip(),
                (data.get("sso_region") or "").strip(),
                (data.get("sso_account_id") or "").strip(),
                (data.get("sso_role_name") or "").strip(),
            )
        except AwsLinkError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    @app.post("/api/mobile/aws/sso/poll")
    def mobile_sso_poll():
        denied = _admin_json()
        if denied:
            return denied
        try:
            return jsonify(aws_connect.poll_sso_device())
        except AwsLinkError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/mobile/scope")
    def mobile_scope():
        denied = _admin_json()
        if denied:
            return denied
        return jsonify(_scope_payload())

    @app.post("/api/mobile/scope/accounts")
    def mobile_scope_account():
        denied = _admin_json()
        if denied:
            return denied
        error = _create_account_from_json(request.get_json(silent=True) or {})
        if error:
            return jsonify({"error": error}), 400
        db.add_audit(session.get("username"), "ACCOUNT_ADDED", "", request.remote_addr)
        return jsonify(_scope_payload())

    @app.post("/api/mobile/scope/delete")
    def mobile_scope_delete():
        denied = _admin_json()
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        table = body.get("table")
        row_id = _maybe_int(body.get("id"))
        if table not in {"customers", "products", "environments", "accounts"} or not row_id:
            return jsonify({"error": "Choose what to remove."}), 400
        db.delete_row(table, row_id)
        db.add_audit(session.get("username"), "SCOPE_DELETED", f"{table}:{row_id}", request.remote_addr)
        return jsonify(_scope_payload())

    @app.get("/api/mobile/people")
    def mobile_people():
        denied = _admin_json()
        if denied:
            return denied
        people = []
        for row in db.get_all_users():
            people.append({
                "username": row["username"],
                "email": row["email"] or "",
                "role": row["role"],
                "active": bool(row["is_active"]),
                "mfa": bool(row["mfa_enrolled"]),
                "last_login": row["last_login"] or "",
            })
        return jsonify({"people": people})

    @app.post("/api/mobile/people")
    def mobile_people_create():
        denied = _admin_json()
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        username = _clean_username(body.get("username"))
        email = (body.get("email") or "").strip()
        password = body.get("password") or ""
        role = body.get("role") if body.get("role") in {"admin", "viewer"} else "viewer"
        if not username or "@" not in email or len(password) < 8:
            return jsonify({"error": "Enter a username, email, and a password of at least 8 characters."}), 400
        if not db.create_user(username, email, db.hash_password(password), role):
            return jsonify({"error": "That username already exists."}), 400
        db.add_audit(session.get("username"), "USER_CREATED", username, request.remote_addr)
        return jsonify({"ok": True, "username": username})

    @app.get("/api/mobile/audit")
    def mobile_audit():
        denied = _admin_json()
        if denied:
            return denied
        logs = []
        for row in db.get_audit_logs(limit=40):
            logs.append({
                "when": charts.when(row["timestamp"]),
                "username": row["username"] or "",
                "action": row["action"] or "",
                "detail": (row["detail"] or "")[:120],
            })
        return jsonify({"logs": logs})

    return app


def _ensure_csrf():
    if not session.get("csrf"):
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def _reject_csrf():
    sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token")
    if session.get("csrf") and sent == session.get("csrf"):
        return None
    message = "The form expired. Refresh the page and try again."
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"error": message}), 400
    _ensure_csrf()
    flash(message, "error")
    return redirect(request.path)


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.get_user_by_id(user_id)
    if not user or not user["is_active"]:
        return None
    return user


def _fully_signed_in():
    user = _current_user()
    if not user:
        return False
    if session.get("auth_method") == "oidc":
        return True
    return bool(session.get("mfa_verified"))


def _start_session(user, method):
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["user_role"] = user["role"]
    session["auth_method"] = method
    session["mfa_verified"] = method == "oidc"
    session["csrf"] = secrets.token_urlsafe(32)
    session.permanent = True


def _safe_next(value):
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return url_for("overview")


def _clean_username(value):
    value = (value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9._-]{3,64}", value):
        return value
    return None


def _unique_username(value):
    base = _clean_username(re.sub(r"[^A-Za-z0-9._-]", "", value or "")) or "user"
    base = base[:50]
    if len(base) < 3:
        base = "user"
    candidate = base
    number = 1
    while db.get_user(candidate):
        number += 1
        candidate = f"{base}-{number}"
    return candidate


def _maybe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _named_user(username):
    if not _clean_username(username):
        return None
    return db.get_user(username)


def _claim_groups(userinfo):
    raw = userinfo.get("groups") or userinfo.get("roles") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _role_from_groups(groups, cfg, existing):
    admin_group = (cfg.get("admin_group") or "").strip()
    if admin_group and groups:
        return "admin" if admin_group in groups else "viewer"
    if existing:
        return existing["role"]
    return "viewer"


def _oidc_client(app):
    cfg = db.get_oidc()
    if not cfg or not cfg["enabled"] or not cfg.get("client_id") or not cfg.get("issuer"):
        return None
    try:
        from authlib.integrations.flask_client import OAuth
    except ImportError:
        return None
    oauth = app.extensions.get("oidc_oauth")
    if oauth is None:
        oauth = OAuth(app)
        app.extensions["oidc_oauth"] = oauth
    registry = getattr(oauth, "_registry", None)
    if isinstance(registry, dict):
        registry.pop("idp", None)
    clients = getattr(oauth, "_clients", None)
    if isinstance(clients, dict):
        clients.pop("idp", None)
    oauth.register(
        name="idp",
        client_id=cfg["client_id"],
        client_secret=cfg.get("client_secret") or "",
        server_metadata_url=cfg["issuer"].rstrip("/") + "/.well-known/openid-configuration",
        client_kwargs={"scope": cfg.get("scopes") or "openid email profile"},
    )
    return oauth.create_client("idp")


def _app_state(user):
    if not user:
        return {}
    tree = db.scope_tree()
    return {
        "mode": db.get_setting("operating_mode") or "msp",
        "cardinality": db.get_setting("product_cardinality") or "single",
        "customers": tree["customers"],
        "products": tree["products"],
        "regions": REGIONS,
        "selection": session.get("selection") or {},
        "role": user["role"],
    }


def _save_connection_form():
    mode = request.form.get("mode") or "unset"
    if mode not in {"profile", "sso", "unset"}:
        mode = "unset"
    profile_name = request.form.get("profile_name") or ""
    sso_region = request.form.get("sso_region") or "us-east-1"
    if sso_region not in REGION_CODES:
        sso_region = "us-east-1"
    db.save_connection(
        mode,
        profile_name,
        request.form.get("sso_start_url") or "",
        sso_region,
        request.form.get("sso_account_id") or "",
        request.form.get("sso_role_name") or "",
    )


def _valid_account_id(value):
    value = (value or "").strip()
    if value.isdigit() and len(value) == 12:
        return value
    return None


def _valid_role(value):
    value = (value or "").strip()
    if not value:
        return ""
    if re.fullmatch(r"[A-Za-z0-9+=,.@_-]{1,64}", value):
        return value
    return None


def _create_initial_scope(wizard):
    account_id = (request.form.get("account_id") or "").strip()
    if not account_id:
        return None
    name = (request.form.get("account_name") or "").strip()
    role = _valid_role(request.form.get("role_name"))
    region = request.form.get("region") or "us-east-1"
    checked = _valid_account_id(account_id)
    if not checked or not name or role is None or region not in REGION_CODES:
        return "Enter a 12-digit account ID, an account name, and an optional role name."
    if wizard.get("mode") == "msp":
        customer = (request.form.get("customer_name") or "").strip()
        if not customer:
            return "Enter the customer name."
        customer_id = db.create_customer(customer)
        db.create_account(checked, name, role, region, customer_id, None, None)
        return None
    product_name = (request.form.get("product_name") or "").strip()
    environment_name = (request.form.get("environment_name") or "").strip()
    if not product_name or not environment_name:
        return "Enter the product name and an environment name."
    product_id = db.create_product(product_name)
    environment_id = db.create_environment(product_id, environment_name)
    db.create_account(checked, name, role, region, None, product_id, environment_id)
    return None


def _finish_setup(wizard):
    if db.get_user(wizard["username"]):
        flash("That administrator username already exists.", "error")
        return redirect(url_for("setup_admin"))
    created = db.create_user(
        wizard["username"], wizard["email"], wizard["password_hash"], role="admin"
    )
    if not created:
        flash("The administrator could not be created.", "error")
        return redirect(url_for("setup_admin"))
    db.set_setting("org_name", wizard["org_name"])
    db.set_setting("operating_mode", wizard["mode"])
    db.set_setting("product_cardinality", wizard["cardinality"])
    db.set_setting("setup_complete", "1")
    db.add_audit(wizard["username"], "SETUP_COMPLETE", wizard["mode"], request.remote_addr)
    session.pop("wizard", None)
    flash("Setup is complete. Sign in and enroll an authenticator.", "success")
    return redirect(url_for("login"))


def _product_exists(product_id):
    return any(product["id"] == product_id for product in db.list_products())


def _admin_json():
    user = _current_user()
    if not user or user["role"] != "admin":
        return jsonify({"error": "Administrator access is required."}), 403
    return None


def _scope_payload():
    tree = db.scope_tree()
    environments = []
    products = []
    for product in tree["products"]:
        products.append({"id": product["id"], "name": product["name"]})
        for env in product["environments"]:
            environments.append({
                "id": env["id"],
                "name": env["name"],
                "product": product["name"],
                "product_id": product["id"],
            })
    return {
        "mode": db.get_setting("operating_mode") or "msp",
        "cardinality": db.get_setting("product_cardinality") or "single",
        "regions": REGIONS,
        "customers": [{"id": item["id"], "name": item["name"]} for item in tree["customers"]],
        "products": products,
        "environments": environments,
        "accounts": [
            {
                "id": item["id"],
                "name": item["name"],
                "account_id": item["account_id"],
                "region": item["default_region"],
                "role_name": item["role_name"] or "",
            }
            for item in tree["accounts"]
        ],
    }


def _create_account_from_json(body):
    account_id = _valid_account_id(body.get("account_id"))
    name = (body.get("name") or "").strip()
    role = _valid_role(body.get("role_name"))
    region = body.get("region") or "ap-south-1"
    if not account_id or not name or role is None or region not in REGION_CODES:
        return "Enter a 12-digit account ID, a name, and a valid role name if you set one."
    mode = db.get_setting("operating_mode")
    if mode == "msp":
        customer_id = _maybe_int(body.get("customer_id"))
        if not customer_id:
            customer_name = (body.get("customer_name") or "").strip()
            if not customer_name:
                return "Choose a customer, or enter a new customer name."
            customer_id = db.create_customer(customer_name)
        elif not any(item["id"] == customer_id for item in db.list_customers()):
            return "Choose a customer for this account."
        db.create_account(account_id, name, role, region, customer_id, None, None)
        return None
    environment_id = _maybe_int(body.get("environment_id"))
    environment = next((item for item in db.list_environments() if item["id"] == environment_id), None)
    if environment:
        product_id = environment["product_id"]
        environment_id = environment["id"]
    else:
        product_name = (body.get("product_name") or "").strip()
        environment_name = (body.get("environment_name") or "").strip()
        if not product_name or not environment_name:
            return "Choose an environment, or enter a product and environment name."
        products = db.list_products()
        if db.get_setting("product_cardinality") == "single" and products:
            product_id = products[0]["id"]
        else:
            product_id = db.create_product(product_name)
        environment_id = db.create_environment(product_id, environment_name)
    db.create_account(account_id, name, role, region, None, product_id, environment_id)
    return None


def _create_account_from_form():
    account_id = _valid_account_id(request.form.get("account_id"))
    name = (request.form.get("name") or "").strip()
    role = _valid_role(request.form.get("role_name"))
    region = request.form.get("region") or "us-east-1"
    if not account_id or not name or role is None or region not in REGION_CODES:
        return "Enter a 12-digit account ID, a name, and a valid role name if you set one."
    mode = db.get_setting("operating_mode")
    if mode == "msp":
        customer_id = _maybe_int(request.form.get("customer_id"))
        if not customer_id or not any(item["id"] == customer_id for item in db.list_customers()):
            return "Choose a customer for this account."
        db.create_account(account_id, name, role, region, customer_id, None, None)
        return None
    environment_id = _maybe_int(request.form.get("environment_id"))
    environment = next((item for item in db.list_environments() if item["id"] == environment_id), None)
    if not environment:
        return "Choose an environment for this account."
    db.create_account(
        account_id,
        name,
        role,
        region,
        None,
        environment["product_id"],
        environment_id,
    )
    return None


def _mobile_document(document):
    def series(items):
        points = []
        for item in items or []:
            try:
                value = float(item.get("value") or 0)
            except (TypeError, ValueError):
                value = 0
            points.append({"label": item.get("label") or "", "value": value})
        return points

    sections = []
    for section in document.get("sections") or []:
        sections.append({
            "title": section.get("title") or "",
            "chart_title": section.get("chart_title") or "",
            "money": bool(section.get("money")),
            "chart": series(section.get("chart")),
            "columns": [str(column) for column in (section.get("columns") or [])],
            "rows": [
                [str(cell) for cell in row]
                for row in (section.get("rows") or [])
            ],
        })
    return {
        "code": document.get("code") or "",
        "domain": document.get("domain") or "",
        "title": document.get("title") or "Report",
        "audience": document.get("audience") or "",
        "summary": document.get("summary") or "",
        "subtitle": document.get("subtitle") or "",
        "money": bool(document.get("money")),
        "kpis": [
            {"label": item.get("label") or "", "value": str(item.get("value") or "")}
            for item in (document.get("kpis") or [])
        ],
        "chart_title": document.get("chart_title") or "",
        "chart": series(document.get("chart")),
        "notes": [str(item) for item in (document.get("notes") or []) if str(item).strip()],
        "sections": sections,
    }


def _scan_brief(row):
    return {
        "when": row.get("when"),
        "kind": row.get("kind"),
        "account_name": row.get("account_name"),
        "region": row.get("region"),
        "total": row.get("total") or 0,
        "high": row.get("high") or 0,
        "actor": row.get("actor") or "",
    }


def _load_scans(limit):
    rows = []
    for row in db.recent_scans(limit):
        try:
            summary = json.loads(row["summary_json"] or "{}")
        except json.JSONDecodeError:
            summary = {}
        rows.append({**row, "summary": summary})
    return charts.present_scans(rows)


def _render_auth(mode, **extra):
    return render_template(
        "auth.html",
        mode=mode,
        step=1 if mode == "password" else 2,
        **extra,
    )


def _collect_report(spec, account, region, aws):
    source = spec["source"]
    ctx = {
        "findings": [],
        "recommendations": [],
        "notes": [],
        "trusted": None,
        "pillars": {},
        "meta": {},
    }
    actor = session.get("username")
    if source == "advisor":
        ctx["trusted"] = advisor.trusted_advisor(aws)
        return ctx
    if source == "native":
        result = advisor.native_recommendations(aws, region)
        ctx["recommendations"] = result.get("recommendations") or []
        ctx["notes"] = result.get("notes") or []
        record_scan("cost", account, region, actor, ctx["recommendations"])
        return ctx
    if source == "inventory":
        scan = scan_all_resources(aws, region)
        recommendations = advisor.rules_from_scan(scan, account["account_id"], region)
        ctx["recommendations"] = recommendations
        ctx["notes"] = [
            "Inventory estimates use published on-demand prices and CloudWatch. "
            "Cost Optimization Hub is the figure that includes this account's discounts."
        ]
        ctx["notes"].extend(scan.get("errors") or [])
        ctx["meta"] = {
            "total_cost": scan.get("total_cost"),
            "actual_30d_ce_cost": scan.get("actual_30d_ce_cost"),
            "total_saving": scan.get("total_saving"),
        }
        record_scan("cost-inventory", account, region, actor, recommendations)
        return ctx
    findings = [
        decorate_finding(item, account["account_id"], region)
        for item in run_all_checks(aws, region)
    ]
    pillars = {name: 0 for name in report_catalog.PILLARS}
    for finding in findings:
        pillars[finding["pillar"]] = pillars.get(finding["pillar"], 0) + 1
    ctx["findings"] = findings
    ctx["pillars"] = pillars
    kind = "governance" if spec["domain"] == "governance" else "housekeeping"
    record_scan(kind, account, region, actor, findings)
    if spec["id"] == "gov-scorecard":
        ctx["trusted"] = advisor.trusted_advisor(aws)
    return ctx


def _open_account():
    data = request.get_json(silent=True) or {}
    region = data.get("region") or "us-east-1"
    if region not in REGION_CODES:
        raise PortalError("Choose a region from the list.")
    account = db.get_account(_maybe_int(data.get("account_pk")))
    if not account:
        raise PortalError("Choose an account in the header.")
    mode = db.get_setting("operating_mode")
    if mode == "msp" and not account["customer_id"]:
        raise PortalError("That account belongs to a product. Switch the operating model, or choose a customer account.")
    if mode == "product" and not account["environment_id"]:
        raise PortalError("That account belongs to a customer. Switch the operating model, or choose an environment account.")
    aws = aws_connect.session_for_account(account, region)
    return account, region, aws
