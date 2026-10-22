"""Persistent study-session history."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.database.db import Database


def create_study_session(
    database: Database, values: dict[str, Any], *, user_id: int | None = None
) -> dict[str, Any]:
    subject = str(values.get("subject", "General")).strip() or "General"
    notes = str(values.get("notes", "")).strip()
    task_id = values.get("task_id")
    duration = values.get("duration_minutes")
    if task_id is not None and (not isinstance(task_id, int) or isinstance(task_id, bool)):
        raise ValueError("task_id must be an integer or null")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 1 <= duration <= 240:
        raise ValueError("duration_minutes must be between 1 and 240")
    try:
        started_at = datetime.fromisoformat(str(values["started_at"]))
        completed_at = datetime.fromisoformat(str(values["completed_at"]))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("started_at and completed_at must be valid ISO datetimes") from error
    if started_at.tzinfo is None or completed_at.tzinfo is None:
        raise ValueError("session timestamps must include a timezone")
    started_at = started_at.astimezone(UTC)
    completed_at = completed_at.astimezone(UTC)
    if completed_at <= started_at:
        raise ValueError("completed_at must be after started_at")

    created_at = datetime.now(UTC).isoformat()
    with database.session() as connection:
        if task_id is not None:
            query = "SELECT id, subject FROM tasks WHERE id = ?"
            parameters = (task_id,)
            if user_id is not None:
                query += " AND user_id = ?"
                parameters = (task_id, user_id)
            task = connection.execute(query, parameters).fetchone()
            if task is None:
                raise ValueError("task_id does not refer to an existing task")
            if not subject or subject == "General":
                subject = task["subject"]
        insert = """INSERT INTO study_sessions
                    (task_id, subject, duration_minutes, notes, started_at, completed_at, created_at, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        parameters = (
            task_id,
            subject,
            duration,
            notes,
            started_at.isoformat(),
            completed_at.isoformat(),
            created_at,
            user_id,
        )
        if database.is_postgres:
            session_id = connection.execute(
                insert + " RETURNING id", parameters
            ).fetchone()["id"]
        else:
            session_id = connection.execute(insert, parameters).lastrowid
        row = connection.execute(
            """SELECT study_sessions.id, study_sessions.task_id, study_sessions.subject,
                      study_sessions.duration_minutes, study_sessions.notes,
                      study_sessions.started_at, study_sessions.completed_at,
                      study_sessions.created_at, tasks.title AS task_title
               FROM study_sessions
               LEFT JOIN tasks ON tasks.id = study_sessions.task_id
               WHERE study_sessions.id = ?""",
            (session_id,),
        ).fetchone()
        return dict(row)


def list_study_sessions(
    database: Database, *, limit: int = 20, offset: int = 0,
    user_id: int | None = None,
) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if offset < 0:
        raise ValueError("offset must not be negative")
    with database.session() as connection:
        owner_filter = " WHERE user_id = ?" if user_id is not None else ""
        parameters: tuple[Any, ...] = (user_id,) if user_id is not None else ()
        totals = connection.execute(
            """SELECT COUNT(*) AS total_sessions,
                      COALESCE(SUM(duration_minutes), 0) AS total_minutes
               FROM study_sessions""" + owner_filter,
            parameters,
        ).fetchone()
        row_query = """SELECT study_sessions.id, study_sessions.task_id, study_sessions.subject,
                      study_sessions.duration_minutes, study_sessions.notes,
                      study_sessions.started_at, study_sessions.completed_at,
                      study_sessions.created_at, tasks.title AS task_title
               FROM study_sessions
               LEFT JOIN tasks ON tasks.id = study_sessions.task_id"""
        if user_id is not None:
            row_query += " WHERE study_sessions.user_id = ?"
        rows = connection.execute(
            row_query + " ORDER BY study_sessions.completed_at DESC, study_sessions.id DESC LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        ).fetchall()
        return {
            "items": [dict(row) for row in rows],
            "total_sessions": totals["total_sessions"],
            "total_minutes": totals["total_minutes"],
        }


def get_focus_time_analysis(
    database: Database, *, today: date | None = None, user_id: int | None = None
) -> dict[str, Any]:
    """Return bounded daily and subject focus totals for the past 30 days."""
    current_day = today or date.today()
    start_day = current_day - timedelta(days=29)
    owner_filter = " AND user_id = ?" if user_id is not None else ""
    parameters: tuple[Any, ...] = (start_day.isoformat(), user_id) if user_id is not None else (start_day.isoformat(),)
    with database.session() as connection:
        daily_rows = connection.execute(
            """SELECT SUBSTR(completed_at, 1, 10) AS study_day,
                      COUNT(*) AS sessions,
                      COALESCE(SUM(duration_minutes), 0) AS minutes
               FROM study_sessions
               WHERE completed_at >= ?""" + owner_filter +
            " GROUP BY SUBSTR(completed_at, 1, 10) ORDER BY study_day",
            parameters,
        ).fetchall()
        subject_rows = connection.execute(
            """SELECT subject, COUNT(*) AS sessions,
                      COALESCE(SUM(duration_minutes), 0) AS minutes
               FROM study_sessions WHERE completed_at >= ?""" + owner_filter +
            " GROUP BY subject ORDER BY minutes DESC, LOWER(subject) LIMIT 20",
            parameters,
        ).fetchall()

    daily = {
        (row["study_day"] if isinstance(row["study_day"], str) else row["study_day"].isoformat()): {
            "sessions": int(row["sessions"]),
            "minutes": int(row["minutes"]),
        }
        for row in daily_rows
    }
    days = [
        {
            "date": (start_day + timedelta(days=offset)).isoformat(),
            **daily.get((start_day + timedelta(days=offset)).isoformat(), {"sessions": 0, "minutes": 0}),
        }
        for offset in range(30)
    ]
    last_7_days = days[-7:]
    active_dates = {entry["date"] for entry in days if entry["sessions"]}
    streak_anchor = current_day if current_day.isoformat() in active_dates else current_day - timedelta(days=1)
    streak = 0
    while streak_anchor.isoformat() in active_dates:
        streak += 1
        streak_anchor -= timedelta(days=1)
    total_minutes = sum(entry["minutes"] for entry in days)
    active_days = len(active_dates)
    return {
        "as_of_date": current_day.isoformat(),
        "last_7_days": {
            "minutes": sum(entry["minutes"] for entry in last_7_days),
            "sessions": sum(entry["sessions"] for entry in last_7_days),
            "daily": last_7_days,
        },
        "last_30_days": {
            "minutes": total_minutes,
            "sessions": sum(entry["sessions"] for entry in days),
            "active_days": active_days,
            "average_minutes_per_active_day": round(total_minutes / active_days) if active_days else 0,
            "current_streak_days": streak,
            "daily": days,
            "by_subject": [dict(row) for row in subject_rows],
        },
    }
