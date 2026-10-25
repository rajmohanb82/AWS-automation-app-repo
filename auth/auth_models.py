"""
Shared Auth Models — SQLite User Database
Location on server: /opt/auth/auth_models.py
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.environ.get("AUTH_DB_PATH", "/opt/auth/users.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            totp_secret TEXT,
            mfa_enrolled INTEGER DEFAULT 0,
            role TEXT DEFAULT 'viewer',
            is_active INTEGER DEFAULT 1,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            created_at TEXT,
            last_login TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT,
            action TEXT NOT NULL,
            detail TEXT,
            ip_address TEXT
        );
    """)
    conn.commit()
    conn.close()


def get_user(username):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_all_users():
    conn = get_db()
    users = conn.execute("SELECT id, username, email, role, mfa_enrolled, is_active, failed_attempts, created_at, last_login FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(u) for u in users]


def create_user(username, email, password_hash, role="viewer"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, email, password_hash, role, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_user_mfa(username, totp_secret, enrolled=True):
    conn = get_db()
    conn.execute(
        "UPDATE users SET totp_secret = ?, mfa_enrolled = ? WHERE username = ?",
        (totp_secret, int(enrolled), username)
    )
    conn.commit()
    conn.close()


def update_last_login(username):
    conn = get_db()
    conn.execute(
        "UPDATE users SET last_login = ?, failed_attempts = 0 WHERE username = ?",
        (datetime.now(timezone.utc).isoformat(), username)
    )
    conn.commit()
    conn.close()


def increment_failed_attempts(username):
    conn = get_db()
    conn.execute("UPDATE users SET failed_attempts = failed_attempts + 1 WHERE username = ?", (username,))
    # Lock after 5 failed attempts for 15 minutes
    user = conn.execute("SELECT failed_attempts FROM users WHERE username = ?", (username,)).fetchone()
    if user and user["failed_attempts"] >= 5:
        from datetime import timedelta
        lock_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        conn.execute("UPDATE users SET locked_until = ? WHERE username = ?", (lock_until, username))
    conn.commit()
    conn.close()


def reset_failed_attempts(username):
    conn = get_db()
    conn.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def is_account_locked(username):
    conn = get_db()
    user = conn.execute("SELECT locked_until FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if not user or not user["locked_until"]:
        return False
    lock_until = datetime.fromisoformat(user["locked_until"])
    if datetime.now(timezone.utc) > lock_until:
        reset_failed_attempts(username)
        return False
    return True


def update_password(username, password_hash):
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
    conn.commit()
    conn.close()


def reset_mfa(username):
    conn = get_db()
    conn.execute("UPDATE users SET totp_secret = NULL, mfa_enrolled = 0 WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def set_user_active(username, active):
    conn = get_db()
    conn.execute("UPDATE users SET is_active = ? WHERE username = ?", (int(active), username))
    conn.commit()
    conn.close()


def add_audit_log(username, action, detail="", ip_address=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_log (timestamp, username, action, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), username, action, detail, ip_address)
    )
    conn.commit()
    conn.close()


def get_audit_logs(limit=100):
    conn = get_db()
    logs = conn.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(l) for l in logs]


# Initialize DB on import
init_db()
