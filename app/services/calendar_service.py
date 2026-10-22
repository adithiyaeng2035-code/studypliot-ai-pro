"""Account-scoped task and focus-session events for the calendar view."""

from datetime import date, timedelta
from typing import Any

from app.database.db import Database


def get_calendar_events(
    database: Database, *, start: date, days: int, user_id: int | None = None
) -> dict[str, list[dict[str, Any]]]:
    if not 1 <= days <= 42:
        raise ValueError("days must be between 1 and 42")
    end = start + timedelta(days=days)
    task_owner = " AND user_id = ?" if user_id is not None else ""
    task_params: tuple[Any, ...] = (start.isoformat(), end.isoformat())
    session_owner = " AND study_sessions.user_id = ?" if user_id is not None else ""
    session_start = (start - timedelta(days=1)).isoformat()
    session_end = (end + timedelta(days=1)).isoformat()
    session_params: tuple[Any, ...] = (session_start, session_end)
    if user_id is not None:
        task_params += (user_id,)
        session_params += (user_id,)

    with database.session() as connection:
        tasks = connection.execute(
            """SELECT id, title, subject, due_date, estimated_minutes, completed
               FROM tasks WHERE due_date >= ? AND due_date < ?""" + task_owner
            + " ORDER BY due_date, completed, id",
            task_params,
        ).fetchall()
        sessions = connection.execute(
            """SELECT study_sessions.id, study_sessions.subject,
                      study_sessions.duration_minutes, study_sessions.started_at,
                      study_sessions.completed_at, tasks.title AS task_title
               FROM study_sessions LEFT JOIN tasks ON tasks.id = study_sessions.task_id
               WHERE study_sessions.started_at >= ? AND study_sessions.started_at < ?"""
            + session_owner + " ORDER BY study_sessions.started_at",
            session_params,
        ).fetchall()

    return {
        "tasks": [dict(row) | {"completed": bool(row["completed"])} for row in tasks],
        "study_sessions": [dict(row) for row in sessions],
    }
