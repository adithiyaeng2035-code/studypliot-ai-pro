"""SQLite and PostgreSQL database access."""

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any


class Database:
    """Creates short-lived connections for application database operations."""

    def __init__(self, target: str | Path):
        target_string = str(target)
        self.is_postgres = target_string == "postgresql" or target_string.startswith(
            ("postgres://", "postgresql://")
        )
        self.target = (
            "" if target_string == "postgresql"
            else target_string if self.is_postgres
            else Path(target)
        )

    def connect(self) -> Any:
        if self.is_postgres:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
            except ImportError as error:
                raise RuntimeError(
                    "PostgreSQL support requires psycopg2-binary. "
                    "Install project requirements before connecting."
                ) from error
            return psycopg2.connect(self.target, cursor_factory=RealDictCursor)

        path = self.target
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Apply ordered SQL migrations, recording each successful version."""
        connection = self.connect()
        try:
            with self.session_from_connection(connection) as session:
                version_type = (
                    "BIGINT PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY"
                )
                session.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    f"version {version_type}, applied_at TEXT NOT NULL)"
                )
                rows = session.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
                applied = {int(row["version"]) for row in rows}

                migration_dir = Path(__file__).with_name("migrations")
                suffix = ".postgres.sql" if self.is_postgres else ".sql"
                migration_files = sorted(
                    path for path in migration_dir.glob("*.sql")
                    if (
                        path.name.endswith(".postgres.sql")
                        if self.is_postgres
                        else not path.name.endswith(".postgres.sql")
                    )
                )
                for migration_path in migration_files:
                    filename = migration_path.name.removesuffix(suffix)
                    match = re.fullmatch(r"(\d+)_([a-z0-9_]+)", filename)
                    if not match:
                        raise RuntimeError(
                            f"Invalid database migration filename: {migration_path.name}"
                        )
                    version = int(match.group(1))
                    if version in applied:
                        continue
                    script = migration_path.read_text(encoding="utf-8")
                    for statement in script.split(";"):
                        if statement.strip():
                            session.execute(statement)
                    session.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                        (version, datetime.now(timezone.utc).isoformat()),
                    )
        finally:
            connection.close()

    @contextmanager
    def session(self) -> Iterator["DatabaseSession"]:
        """Yield a connection that commits on success and rolls back on error."""
        connection = self.connect()
        session = DatabaseSession(connection, self.is_postgres)
        try:
            yield session
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def session_from_connection(self, connection: Any) -> Iterator["DatabaseSession"]:
        session = DatabaseSession(connection, self.is_postgres)
        try:
            yield session
            connection.commit()
        except Exception:
            connection.rollback()
            raise


class DatabaseSession:
    """Small execute-compatible wrapper over SQLite and PostgreSQL."""

    def __init__(self, connection: Any, is_postgres: bool):
        self.connection = connection
        self.is_postgres = is_postgres

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> Any:
        if not self.is_postgres:
            return self.connection.execute(query, parameters)
        cursor = self.connection.cursor()
        cursor.execute(query.replace("?", "%s"), parameters)
        return cursor
