"""Operational CLI.

    python -m app.cli seed-reference
    python -m app.cli create-admin --email admin@example.com --name "Ops Admin"
    python -m app.cli seed-demo            # demo environment only (DEMO_MODE=true)
    python -m app.cli reset-demo --yes     # wipe + rebuild the demo database (DEMO_MODE=true only)
    python -m app.cli check-locales
"""
from __future__ import annotations

import argparse
import getpass
import secrets
import sys

from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import system_session


def seed_reference() -> None:
    from app.seed.reference import seed_reference as run

    with system_session() as db:
        run(db)
        db.commit()
    print("reference data seeded")


def create_admin(email: str, name: str, phone: str | None, password: str | None) -> None:
    from app.core.security import hash_password, password_problems
    from app.core.utils import normalize_phone, utcnow
    from app.models.enums import UserStatus
    from app.models.identity import Role, User, UserRole

    generated = False
    if not password:
        if sys.stdin.isatty():
            password = getpass.getpass("Admin password (leave empty to generate): ") or None
        if not password:
            password = secrets.token_urlsafe(18) + "aA1!"
            generated = True
    problems = password_problems(password, email=email)
    if problems:
        raise SystemExit(f"weak password: {problems}")
    with system_session() as db:
        if db.scalar(select(User).where(func.lower(User.email) == email.lower())):
            raise SystemExit("a user with this email already exists")
        user = User(email=email.lower(), phone=normalize_phone(phone) if phone else None, full_name=name,
                    password_hash=hash_password(password), status=UserStatus.active, email_verified_at=utcnow(),
                    terms_version="1.0", terms_accepted_at=utcnow(), password_changed_at=utcnow())
        db.add(user)
        db.flush()
        role = db.scalar(select(Role).where(Role.code == "platform_admin"))
        if role is None:
            raise SystemExit("run seed-reference first")
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
    print(f"platform admin created: {email}")
    if generated:
        print("generated password (shown once, store it in a password manager):")
        print(password)
    print("Sign in and enable two-factor authentication (required for admin pages).")


def seed_demo(force: bool) -> None:
    if settings.is_production and not force:
        raise SystemExit("refusing to seed demo data in production")
    if not settings.demo_mode and not force:
        raise SystemExit("set DEMO_MODE=true (demo environment) or pass --force for local development")
    from app.seed.demo import seed_demo as run

    run()


def reset_demo(yes: bool) -> None:
    """Drop every table in the DEMO database, migrate, and reseed reference + demo data."""
    if settings.is_production or not settings.demo_mode:
        raise SystemExit("reset-demo only runs with DEMO_MODE=true outside production")
    if not yes:
        raise SystemExit("this erases the demo database; re-run with --yes")
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    import pathlib

    owner = create_engine(settings.database_owner_url)
    with owner.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    owner.dispose()
    cfg = Config(str(pathlib.Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(pathlib.Path(__file__).resolve().parents[1] / "alembic"))
    cfg.attributes["url"] = settings.database_owner_url
    command.upgrade(cfg, "head")
    seed_reference()
    from app.seed.demo import seed_demo as run

    run()


def check_locales() -> None:
    from app.core.i18n import missing_keys

    missing = missing_keys()
    bad = {k: v for k, v in missing.items() if v}
    for loc, keys in bad.items():
        print(f"{loc}: {len(keys)} missing → {keys[:20]}")
    if bad:
        raise SystemExit(1)
    print("backend locales complete")


def main() -> None:
    parser = argparse.ArgumentParser(prog="wesal")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-reference")
    p = sub.add_parser("create-admin")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--phone")
    p.add_argument("--password", help="avoid on shared shells; prompts or generates when omitted")
    d = sub.add_parser("seed-demo")
    d.add_argument("--force", action="store_true")
    rd = sub.add_parser("reset-demo")
    rd.add_argument("--yes", action="store_true")
    sub.add_parser("check-locales")
    args = parser.parse_args()
    if args.cmd == "seed-reference":
        seed_reference()
    elif args.cmd == "create-admin":
        create_admin(args.email, args.name, args.phone, args.password)
    elif args.cmd == "seed-demo":
        seed_demo(args.force)
    elif args.cmd == "reset-demo":
        reset_demo(args.yes)
    elif args.cmd == "check-locales":
        check_locales()


if __name__ == "__main__":
    main()
