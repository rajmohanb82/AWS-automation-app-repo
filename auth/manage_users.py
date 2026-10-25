#!/usr/bin/env python3
"""
User Management CLI — Create/manage users from command line.
Location on server: /opt/auth/manage_users.py

Usage:
    python3 /opt/auth/manage_users.py create --username admin --email admin@co.com --password "Pass123!" --role admin
    python3 /opt/auth/manage_users.py list
    python3 /opt/auth/manage_users.py reset-password --username admin --password "NewPass!"
    python3 /opt/auth/manage_users.py reset-mfa --username admin
    python3 /opt/auth/manage_users.py disable --username admin
    python3 /opt/auth/manage_users.py enable --username admin
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bcrypt
from auth_models import (
    create_user, get_user, get_all_users, update_password,
    reset_mfa, set_user_active, init_db
)


def hash_pw(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def cmd_create(args):
    if len(args.password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        sys.exit(1)

    pw_hash = hash_pw(args.password)
    success = create_user(args.username, args.email, pw_hash, args.role)
    if success:
        print(f"✅ User '{args.username}' created (role={args.role})")
    else:
        print(f"❌ User '{args.username}' already exists.")
        sys.exit(1)


def cmd_list(args):
    users = get_all_users()
    if not users:
        print("No users found.")
        return
    print(f"{'Username':<20} {'Email':<30} {'Role':<8} {'MFA':<5} {'Active':<7} {'Last Login'}")
    print("-" * 100)
    for u in users:
        mfa = "Yes" if u["mfa_enrolled"] else "No"
        active = "Yes" if u["is_active"] else "No"
        last = u["last_login"] or "Never"
        print(f"{u['username']:<20} {u['email']:<30} {u['role']:<8} {mfa:<5} {active:<7} {last}")


def cmd_reset_password(args):
    user = get_user(args.username)
    if not user:
        print(f"❌ User '{args.username}' not found.")
        sys.exit(1)
    pw_hash = hash_pw(args.password)
    update_password(args.username, pw_hash)
    print(f"✅ Password reset for '{args.username}'")


def cmd_reset_mfa(args):
    user = get_user(args.username)
    if not user:
        print(f"❌ User '{args.username}' not found.")
        sys.exit(1)
    reset_mfa(args.username)
    print(f"✅ MFA reset for '{args.username}' — will need to re-enroll on next login")


def cmd_disable(args):
    user = get_user(args.username)
    if not user:
        print(f"❌ User '{args.username}' not found.")
        sys.exit(1)
    set_user_active(args.username, False)
    print(f"✅ User '{args.username}' disabled")


def cmd_enable(args):
    user = get_user(args.username)
    if not user:
        print(f"❌ User '{args.username}' not found.")
        sys.exit(1)
    set_user_active(args.username, True)
    print(f"✅ User '{args.username}' enabled")


if __name__ == "__main__":
    init_db()

    parser = argparse.ArgumentParser(description="User Management CLI")
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="Create a new user")
    p_create.add_argument("--username", required=True)
    p_create.add_argument("--email", required=True)
    p_create.add_argument("--password", required=True)
    p_create.add_argument("--role", default="viewer", choices=["admin", "viewer"])

    # list
    sub.add_parser("list", help="List all users")

    # reset-password
    p_rp = sub.add_parser("reset-password", help="Reset user password")
    p_rp.add_argument("--username", required=True)
    p_rp.add_argument("--password", required=True)

    # reset-mfa
    p_rm = sub.add_parser("reset-mfa", help="Reset user MFA")
    p_rm.add_argument("--username", required=True)

    # disable
    p_dis = sub.add_parser("disable", help="Disable a user")
    p_dis.add_argument("--username", required=True)

    # enable
    p_en = sub.add_parser("enable", help="Enable a user")
    p_en.add_argument("--username", required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "create": cmd_create,
        "list": cmd_list,
        "reset-password": cmd_reset_password,
        "reset-mfa": cmd_reset_mfa,
        "disable": cmd_disable,
        "enable": cmd_enable,
    }
    cmds[args.command](args)
