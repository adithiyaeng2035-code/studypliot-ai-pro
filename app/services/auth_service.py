"""Password authentication and server-side browser sessions."""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from pwdlib import PasswordHash

from app.config import AUTH_ALLOW_REGISTRATION
from app.database.db import Database

SESSION_LIFETIME = timedelta(hours=12)
LOGIN_WINDOW = timedelta(minutes=15)
MAX_LOGIN_ATTEMPTS = 10
PASSWORD_HASHER = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRateLimited(RuntimeError):
    """Raised when an email and source address exceed the login attempt limit."""


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("enter a valid email address")
    return normalized


def register_user(
    database: Database,
    *,
    email: str,
    password: str,
    full_name: str,
) -> dict[str, Any]:
    normalized_email = normalize_email(email)
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    if len(password) > 128:
        raise ValueError("password must be 128 characters or fewer")
    normalized_name = full_name.strip()
    if not normalized_name:
        raise ValueError("student name is required")
    if len(normalized_name) > 120:
        raise ValueError("name must be 120 characters or fewer")

    now = datetime.now(timezone.utc).isoformat()
    with database.session() as connection:
        user_count = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if not AUTH_ALLOW_REGISTRATION:
            raise PermissionError("new account registration is disabled")

        password_hash = PASSWORD_HASHER.hash(password)
        insert = """INSERT INTO users (email, full_name, password_hash, created_at)
                    VALUES (?, ?, ?, ?)"""
        try:
            if database.is_postgres:
                user_id = connection.execute(
                    insert + " RETURNING id",
                    (normalized_email, normalized_name, password_hash, now),
                ).fetchone()["id"]
            else:
                user_id = connection.execute(
                insert, (normalized_email, normalized_name, password_hash, now)
                ).lastrowid
        except Exception as error:
            if "unique" in str(error).lower() or "duplicate key" in str(error).lower():
                raise ValueError("an account with this email already exists") from error
            raise

        if user_count == 0:
            connection.execute("UPDATE tasks SET user_id = ? WHERE user_id IS NULL", (user_id,))
            connection.execute(
                "UPDATE study_sessions SET user_id = ? WHERE user_id IS NULL", (user_id,)
            )
        return {"id": int(user_id), "email": normalized_email, "full_name": normalized_name}


def authenticate_user(
    database: Database, *, email: str, password: str, source_address: str = "unknown"
) -> dict[str, Any] | None:
    try:
        normalized_email = normalize_email(email)
    except ValueError:
        normalized_email = ""
    fingerprint = hashlib.sha256(
        f"{normalized_email}|{source_address}".encode("utf-8")
    ).hexdigest()
    now = datetime.now(timezone.utc)
    cutoff = (now - LOGIN_WINDOW).isoformat()
    with database.session() as connection:
        connection.execute(
            "DELETE FROM auth_login_attempts WHERE attempted_at < ?", (cutoff,)
        )
        attempts = connection.execute(
            "SELECT COUNT(*) AS total FROM auth_login_attempts "
            "WHERE fingerprint = ? AND attempted_at >= ?",
            (fingerprint, cutoff),
        ).fetchone()["total"]
        if attempts >= MAX_LOGIN_ATTEMPTS:
            raise LoginRateLimited("too many sign-in attempts; try again later")
        user = connection.execute(
            "SELECT id, email, full_name, password_hash FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
    password_hash = user["password_hash"] if user else DUMMY_PASSWORD_HASH
    try:
        valid = PASSWORD_HASHER.verify(password, password_hash)
    except (ValueError, TypeError):
        valid = False
    if not user or not valid:
        with database.session() as connection:
            connection.execute(
                "INSERT INTO auth_login_attempts (fingerprint, attempted_at) VALUES (?, ?)",
                (fingerprint, now.isoformat()),
            )
        return None
    with database.session() as connection:
        connection.execute(
            "DELETE FROM auth_login_attempts WHERE fingerprint = ?", (fingerprint,)
        )
    return {"id": int(user["id"]), "email": user["email"], "full_name": user["full_name"]}


def create_session(database: Database, user_id: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    now = datetime.now(timezone.utc)
    with database.session() as connection:
        connection.execute(
            "DELETE FROM auth_sessions WHERE expires_at <= ?", (now.isoformat(),)
        )
        connection.execute(
            """INSERT INTO auth_sessions
               (token_hash, user_id, csrf_token, expires_at, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                token_hash,
                user_id,
                csrf_token,
                (now + SESSION_LIFETIME).isoformat(),
                now.isoformat(),
            ),
        )
    return token, csrf_token


def resolve_session(database: Database, token: str | None) -> dict[str, Any] | None:
    if not token or len(token) > 128:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with database.session() as connection:
        row = connection.execute(
            """SELECT users.id, users.email, users.full_name,
                      auth_sessions.token_hash, auth_sessions.csrf_token
               FROM auth_sessions JOIN users ON users.id = auth_sessions.user_id
               WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?""",
            (token_hash, now),
        ).fetchone()
    return dict(row) if row else None


def revoke_session(database: Database, token: str | None) -> None:
    if not token or len(token) > 128:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with database.session() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))


def delete_account(database: Database, user_id: int, password: str) -> bool:
    """Verify the user's password, then permanently remove their account data."""
    with database.session() as connection:
        user = connection.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user is None:
            return False
        try:
            valid = PASSWORD_HASHER.verify(password, user["password_hash"])
        except (ValueError, TypeError):
            valid = False
        if not valid:
            return False
        connection.execute("DELETE FROM study_sessions WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return True
