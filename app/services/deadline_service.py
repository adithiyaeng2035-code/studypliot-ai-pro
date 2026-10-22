"""Deadline summaries for dashboard and planning views."""

from datetime import date, timedelta
from typing import Any

from app.database.db import Database


def get_deadlines(
    database: Database, *, today: date | None = None, days: int = 7, limit: int = 10,
    user_id: int | None = None,
) -> dict[str, Any]:
    if not 1 <= days <= 90:
        raise ValueError("days must be between 1 and 90")
    if not 1 <= limit <= 25:
        raise ValueError("limit must be between 1 and 25")
    start = today or date.today()
    end = start + timedelta(days=days)
    owner_filter = " AND user_id = ?" if user_id is not None else ""
    owner_parameters = (user_id,) if user_id is not None else ()
    with database.session() as connection:
        overdue_count = connection.execute(
            """SELECT COUNT(*) AS total FROM tasks
               WHERE completed = 0 AND due_date < ?""" + owner_filter,
            (start.isoformat(), *owner_parameters),
        ).fetchone()["total"]
        upcoming_count = connection.execute(
            """SELECT COUNT(*) AS total FROM tasks
               WHERE completed = 0 AND due_date >= ? AND due_date <= ?""" + owner_filter,
            (start.isoformat(), end.isoformat(), *owner_parameters),
        ).fetchone()["total"]
        overdue = connection.execute(
            """SELECT id, title, subject, due_date, estimated_minutes
               FROM tasks WHERE completed = 0 AND due_date < ?""" + owner_filter +
            " ORDER BY due_date ASC, id ASC LIMIT ?",
            (start.isoformat(), *owner_parameters, limit),
        ).fetchall()
        upcoming = connection.execute(
            """SELECT id, title, subject, due_date, estimated_minutes
               FROM tasks WHERE completed = 0 AND due_date >= ? AND due_date <= ?""" +
            owner_filter + " ORDER BY due_date ASC, id ASC LIMIT ?",
            (start.isoformat(), end.isoformat(), *owner_parameters, limit),
        ).fetchall()
    return {
        "overdue": [dict(row) for row in overdue],
        "upcoming": [dict(row) for row in upcoming],
        "overdue_count": overdue_count,
        "upcoming_count": upcoming_count,
    }
