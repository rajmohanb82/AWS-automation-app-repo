"""SQLite storage for the operations console."""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PORTAL_DB", ROOT / "data" / "portal.db"))


def utcnow():
    return datetime.now(timezone.utc)


def iso(moment=None):
    return (moment or utcnow()).isoformat()


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT,
            oidc_sub TEXT UNIQUE,
            totp_secret TEXT,
            mfa_enrolled INTEGER DEFAULT 0,
            role TEXT DEFAULT 'viewer',
            is_active INTEGER DEFAULT 1,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            created_at TEXT,
            last_login TEXT
        );

        CREATE TABLE IF NOT EXISTS oidc_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled INTEGER DEFAULT 0,
            issuer TEXT,
            client_id TEXT,
            client_secret TEXT,
            redirect_uri TEXT,
            scopes TEXT DEFAULT 'openid email profile',
            label TEXT DEFAULT 'Identity provider',
            admin_group TEXT
        );

        CREATE TABLE IF NOT EXISTS aws_connection (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mode TEXT DEFAULT 'unset',
            profile_name TEXT,
            sso_start_url TEXT,
            sso_region TEXT,
            sso_account_id TEXT,
            sso_role_name TEXT,
            sso_client_id TEXT,
            sso_client_secret TEXT,
            sso_access_token TEXT,
            sso_refresh_token TEXT,
            sso_token_expires_at TEXT,
            pending_client_id TEXT,
            pending_client_secret TEXT,
            pending_device_code TEXT,
            pending_interval INTEGER
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS environments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            name TEXT NOT NULL,
            role_name TEXT,
            default_region TEXT DEFAULT 'us-east-1',
            customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            environment_id INTEGER REFERENCES environments(id) ON DELETE CASCADE,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT,
            action TEXT NOT NULL,
            detail TEXT,
            ip_address TEXT
        );

        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            aws_account_id TEXT,
            account_name TEXT,
            region TEXT,
            actor TEXT,
            summary_json TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS integration_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT,
            delivered INTEGER DEFAULT 0
        );
        """
    )
    conn.execute("INSERT OR IGNORE INTO oidc_config (id) VALUES (1)")
    conn.execute("INSERT OR IGNORE INTO aws_connection (id) VALUES (1)")
    conn.commit()
    conn.close()


def _one(sql, params=()):
    conn = connect()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


def _all(sql, params=()):
    conn = connect()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _exec(sql, params=()):
    conn = connect()
    cur = conn.execute(sql, params)
    conn.commit()
    last = cur.lastrowid
    conn.close()
    return last


def get_setting(key, default=None):
    row = _one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key, value):
    _exec(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def setup_complete():
    return get_setting("setup_complete") == "1"


def secret_key():
    current = get_setting("secret_key")
    if current:
        return current
    value = secrets.token_hex(32)
    set_setting("secret_key", value)
    return value


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    if not stored or not stored.startswith("pbkdf2$"):
        return False
    try:
        _, salt_hex, digest_hex = stored.split("$", 2)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 200_000
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def add_audit(username, action, detail="", ip_address=""):
    _exec(
        "INSERT INTO audit_log (timestamp, username, action, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
        (iso(), username, action, detail, ip_address),
    )


def get_audit_logs(limit=200):
    return _all(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    )


def create_user(username, email, password_hash, role="viewer", oidc_sub=None):
    try:
        return _exec(
            """
            INSERT INTO users (username, email, password_hash, oidc_sub, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, email, password_hash, oidc_sub, role, iso()),
        )
    except sqlite3.IntegrityError:
        return None


def get_user(username):
    return _one("SELECT * FROM users WHERE username = ?", (username,))


def get_user_by_id(user_id):
    return _one("SELECT * FROM users WHERE id = ?", (user_id,))


def get_user_by_oidc(sub):
    return _one("SELECT * FROM users WHERE oidc_sub = ?", (sub,))


def get_all_users():
    return _all(
        """
        SELECT id, username, email, role, mfa_enrolled, is_active, failed_attempts,
               created_at, last_login, oidc_sub
        FROM users ORDER BY created_at DESC
        """
    )


def count_active_admins(exclude_id=None):
    if exclude_id is None:
        row = _one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1")
    else:
        row = _one(
            "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?",
            (exclude_id,),
        )
    return row["n"] if row else 0


def update_password(username, password_hash):
    _exec("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))


def update_user_mfa(username, totp_secret, enrolled):
    _exec(
        "UPDATE users SET totp_secret = ?, mfa_enrolled = ? WHERE username = ?",
        (totp_secret, int(enrolled), username),
    )


def update_last_login(username):
    _exec(
        "UPDATE users SET last_login = ?, failed_attempts = 0, locked_until = NULL WHERE username = ?",
        (iso(), username),
    )


def set_user_role(username, role):
    _exec("UPDATE users SET role = ? WHERE username = ?", (role, username))


def set_user_active(username, active):
    _exec("UPDATE users SET is_active = ? WHERE username = ?", (int(active), username))


def reset_mfa(username):
    _exec(
        "UPDATE users SET totp_secret = NULL, mfa_enrolled = 0 WHERE username = ?",
        (username,),
    )


def increment_failed_attempts(username):
    conn = connect()
    conn.execute(
        "UPDATE users SET failed_attempts = failed_attempts + 1 WHERE username = ?",
        (username,),
    )
    user = conn.execute(
        "SELECT failed_attempts FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if user and user["failed_attempts"] >= 5:
        lock_until = iso(utcnow() + timedelta(minutes=15))
        conn.execute(
            "UPDATE users SET locked_until = ? WHERE username = ?",
            (lock_until, username),
        )
    conn.commit()
    conn.close()


def is_account_locked(username):
    user = get_user(username)
    if not user or not user["locked_until"]:
        return False
    locked = datetime.fromisoformat(user["locked_until"])
    if locked > utcnow():
        return True
    _exec(
        "UPDATE users SET locked_until = NULL, failed_attempts = 0 WHERE username = ?",
        (username,),
    )
    return False


def get_oidc():
    return _one("SELECT * FROM oidc_config WHERE id = 1")


def save_oidc(enabled, issuer, client_id, client_secret, redirect_uri, scopes, label, admin_group):
    current = get_oidc() or {}
    secret = client_secret or current.get("client_secret") or ""
    _exec(
        """
        UPDATE oidc_config
        SET enabled = ?, issuer = ?, client_id = ?, client_secret = ?, redirect_uri = ?,
            scopes = ?, label = ?, admin_group = ?
        WHERE id = 1
        """,
        (
            int(enabled),
            issuer.strip(),
            client_id.strip(),
            secret,
            redirect_uri.strip(),
            scopes.strip() or "openid email profile",
            label.strip() or "Identity provider",
            admin_group.strip(),
        ),
    )


def get_connection():
    return _one("SELECT * FROM aws_connection WHERE id = 1")


def save_connection(mode, profile_name, sso_start_url, sso_region, sso_account_id, sso_role_name):
    _exec(
        """
        UPDATE aws_connection
        SET mode = ?, profile_name = ?, sso_start_url = ?, sso_region = ?,
            sso_account_id = ?, sso_role_name = ?
        WHERE id = 1
        """,
        (
            mode,
            (profile_name or "").strip(),
            (sso_start_url or "").strip(),
            (sso_region or "").strip(),
            (sso_account_id or "").strip(),
            (sso_role_name or "").strip(),
        ),
    )


def save_sso_pending(client_id, client_secret, device_code, interval):
    _exec(
        """
        UPDATE aws_connection
        SET pending_client_id = ?, pending_client_secret = ?, pending_device_code = ?, pending_interval = ?
        WHERE id = 1
        """,
        (client_id, client_secret, device_code, int(interval or 1)),
    )


def save_sso_token(client_id, client_secret, access_token, refresh_token, expires_at):
    _exec(
        """
        UPDATE aws_connection
        SET sso_client_id = ?, sso_client_secret = ?, sso_access_token = ?,
            sso_refresh_token = ?, sso_token_expires_at = ?,
            pending_client_id = NULL, pending_client_secret = NULL,
            pending_device_code = NULL, pending_interval = NULL
        WHERE id = 1
        """,
        (client_id, client_secret, access_token, refresh_token, expires_at),
    )


def clear_sso_pending():
    _exec(
        """
        UPDATE aws_connection
        SET pending_client_id = NULL, pending_client_secret = NULL,
            pending_device_code = NULL, pending_interval = NULL
        WHERE id = 1
        """
    )


def create_customer(name):
    return _exec(
        "INSERT INTO customers (name, created_at) VALUES (?, ?)",
        (name.strip(), iso()),
    )


def create_product(name):
    return _exec(
        "INSERT INTO products (name, created_at) VALUES (?, ?)",
        (name.strip(), iso()),
    )


def create_environment(product_id, name):
    count = _one(
        "SELECT COUNT(*) AS n FROM environments WHERE product_id = ?",
        (product_id,),
    )
    return _exec(
        "INSERT INTO environments (product_id, name, sort_order, created_at) VALUES (?, ?, ?, ?)",
        (product_id, name.strip(), count["n"] if count else 0, iso()),
    )


def create_account(account_id, name, role_name, default_region, customer_id, product_id, environment_id):
    return _exec(
        """
        INSERT INTO accounts (
            account_id, name, role_name, default_region, customer_id, product_id, environment_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account_id.strip(),
            name.strip(),
            (role_name or "").strip(),
            default_region,
            customer_id,
            product_id,
            environment_id,
            iso(),
        ),
    )


def get_account(account_pk):
    return _one("SELECT * FROM accounts WHERE id = ?", (account_pk,))


def delete_row(table, row_id):
    if table not in {"customers", "products", "environments", "accounts"}:
        raise ValueError("Unknown table")
    _exec(f"DELETE FROM {table} WHERE id = ?", (row_id,))


def list_customers():
    return _all("SELECT * FROM customers ORDER BY name COLLATE NOCASE")


def list_products():
    return _all("SELECT * FROM products ORDER BY name COLLATE NOCASE")


def list_environments(product_id=None):
    if product_id is None:
        return _all(
            """
            SELECT environments.*, products.name AS product_name
            FROM environments JOIN products ON products.id = environments.product_id
            ORDER BY products.name, environments.sort_order, environments.name
            """
        )
    return _all(
        "SELECT * FROM environments WHERE product_id = ? ORDER BY sort_order, name",
        (product_id,),
    )


def list_accounts():
    return _all("SELECT * FROM accounts ORDER BY name COLLATE NOCASE")


def scope_tree():
    accounts = list_accounts()
    customers = []
    for customer in list_customers():
        customers.append(
            {
                **customer,
                "accounts": [a for a in accounts if a["customer_id"] == customer["id"]],
            }
        )
    products = []
    for product in list_products():
        environments = []
        for env in list_environments(product["id"]):
            environments.append(
                {
                    **env,
                    "accounts": [a for a in accounts if a["environment_id"] == env["id"]],
                }
            )
        products.append({**product, "environments": environments})
    return {"customers": customers, "products": products, "accounts": accounts}


def add_scan(kind, aws_account_id, account_name, region, actor, summary_json):
    return _exec(
        """
        INSERT INTO scans (kind, aws_account_id, account_name, region, actor, summary_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (kind, aws_account_id, account_name, region, actor, summary_json, iso()),
    )


def recent_scans(limit=8):
    return _all("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,))


def add_event(event_type, payload_json):
    return _exec(
        "INSERT INTO integration_events (event_type, payload_json, created_at, delivered) VALUES (?, ?, ?, 0)",
        (event_type, payload_json, iso()),
    )


def recent_events(limit=100):
    return _all(
        "SELECT * FROM integration_events ORDER BY id DESC LIMIT ?",
        (limit,),
    )
