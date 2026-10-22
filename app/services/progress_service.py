"""Study progress summaries."""

from datetime import date, timedelta
from typing import Any

from app.database.db import Database


def get_progress(database: Database, *, user_id: int | None = None) -> dict[str, Any]:
    owner_clause = "user_id = ?" if user_id is not None else "1 = 1"
    owner_parameters = (user_id,) if user_id is not None else ()
    with database.session() as connection:
        totals = connection.execute(
            """SELECT COUNT(*) AS total,
                      COALESCE(SUM(completed), 0) AS completed,
                      COALESCE(SUM(CASE WHEN completed = 1 THEN estimated_minutes ELSE 0 END), 0)
                          AS completed_minutes
               FROM tasks WHERE """ + owner_clause,
            owner_parameters,
        ).fetchone()
        subjects = connection.execute(
            """SELECT subject, COUNT(*) AS total,
                      COALESCE(SUM(completed), 0) AS completed
               FROM tasks WHERE """ + owner_clause +
            " GROUP BY subject ORDER BY LOWER(subject)",
            owner_parameters,
        ).fetchall()
        focus_totals = connection.execute(
            """SELECT COUNT(*) AS sessions,
                      COALESCE(SUM(duration_minutes), 0) AS minutes
               FROM study_sessions WHERE """ + owner_clause,
            owner_parameters,
        ).fetchone()
    total = totals["total"]
    completed = totals["completed"]
    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "open_tasks": total - completed,
        "completion_percent": round(completed * 100 / total) if total else 0,
        "completed_minutes": totals["completed_minutes"],
        "focus_sessions": focus_totals["sessions"],
        "focus_minutes": focus_totals["minutes"],
        "by_subject": [dict(row) for row in subjects],
    }


def get_progress_analysis_context(
    database: Database, *, today: date | None = None, user_id: int | None = None
) -> dict[str, Any]:
    """Build bounded, database-derived evidence for an AI progress review."""
    current_day = today or date.today()
    recent_start = current_day - timedelta(days=29)
    owner_clause = "user_id = ?" if user_id is not None else "1 = 1"
    owner_parameters = (user_id,) if user_id is not None else ()
    with database.session() as connection:
        subject_rows = connection.execute(
            """SELECT subject, COUNT(*) AS total,
                      COALESCE(SUM(completed), 0) AS completed
               FROM tasks WHERE """ + owner_clause +
            " GROUP BY subject ORDER BY COUNT(*) DESC, LOWER(subject) LIMIT 20",
            owner_parameters,
        ).fetchall()
        totals = connection.execute(
            """SELECT COUNT(*) AS total,
                      COALESCE(SUM(completed), 0) AS completed,
                      COALESCE(SUM(CASE WHEN completed = 1 THEN estimated_minutes ELSE 0 END), 0)
                          AS completed_minutes
               FROM tasks WHERE """ + owner_clause,
            owner_parameters,
        ).fetchone()
        task_counts = connection.execute(
            """SELECT
                   COALESCE(SUM(CASE WHEN completed = 0 AND due_date < ? THEN 1 ELSE 0 END), 0)
                       AS overdue_open,
                   COALESCE(SUM(CASE WHEN completed = 0 AND due_date >= ?
                       AND due_date <= ? THEN 1 ELSE 0 END), 0) AS due_within_7_days,
                   COALESCE(SUM(CASE WHEN completed = 1 AND completed_at >= ?
                       THEN 1 ELSE 0 END), 0) AS completed_in_30_days
               FROM tasks WHERE """ + owner_clause,
            (
                current_day.isoformat(),
                current_day.isoformat(),
                (current_day + timedelta(days=7)).isoformat(),
                recent_start.isoformat(),
                *owner_parameters,
            ),
        ).fetchone()
        focus_counts = connection.execute(
            """SELECT COUNT(*) AS sessions,
                      COALESCE(SUM(duration_minutes), 0) AS minutes
               FROM study_sessions
               WHERE completed_at >= ? AND """ + owner_clause,
            (recent_start.isoformat(), *owner_parameters),
        ).fetchone()

    total = totals["total"]
    completed = totals["completed"]
    return {
        "as_of_date": current_day.isoformat(),
        "progress": {
            "total_tasks": total,
            "completed_tasks": completed,
            "open_tasks": total - completed,
            "completion_percent": round(completed * 100 / total) if total else 0,
            "completed_minutes": totals["completed_minutes"],
        },
        "subject_progress": [dict(row) for row in subject_rows],
        "overdue_open_tasks": task_counts["overdue_open"],
        "open_tasks_due_within_7_days": task_counts["due_within_7_days"],
        "tasks_completed_in_last_30_days": task_counts["completed_in_30_days"],
        "focus_sessions_in_last_30_days": focus_counts["sessions"],
        "focus_minutes_in_last_30_days": focus_counts["minutes"],
    }
