"""Bounded daily progress history for dashboards."""

from datetime import date, timedelta
from typing import Any

from app.database.db import Database


def get_progress_trends(
    database: Database, *, days: int = 30, today: date | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    if not 7 <= days <= 90:
        raise ValueError("days must be between 7 and 90")
    end = today or date.today()
    start = end - timedelta(days=days - 1)
    task_owner = " AND user_id = ?" if user_id is not None else ""
    session_owner = " AND user_id = ?" if user_id is not None else ""
    task_params: tuple[Any, ...] = (start.isoformat(), (end + timedelta(days=1)).isoformat())
    session_params = task_params
    if user_id is not None:
        task_params += (user_id,)
        session_params += (user_id,)
    with database.session() as connection:
        tasks = connection.execute(
            """SELECT substr(completed_at, 1, 10) AS day, subject, COUNT(*) AS completed
               FROM tasks WHERE completed = 1 AND completed_at >= ? AND completed_at < ?"""
            + task_owner + " GROUP BY substr(completed_at, 1, 10), subject", task_params,
        ).fetchall()
        sessions = connection.execute(
            """SELECT substr(completed_at, 1, 10) AS day,
                      COUNT(*) AS sessions, COALESCE(SUM(duration_minutes), 0) AS minutes
               FROM study_sessions WHERE completed_at >= ? AND completed_at < ?"""
            + session_owner + " GROUP BY substr(completed_at, 1, 10)", session_params,
        ).fetchall()
    task_by_day: dict[str, int] = {}
    subjects_by_day: dict[str, list[dict[str, Any]]] = {}
    for row in tasks:
        task_by_day[row["day"]] = task_by_day.get(row["day"], 0) + int(row["completed"])
        subjects_by_day.setdefault(row["day"], []).append({
            "subject": row["subject"], "completed": int(row["completed"]),
        })
    session_by_day = {row["day"]: row for row in sessions}
    points = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).isoformat()
        session = session_by_day.get(day)
        points.append({
            "date": day,
            "completed_tasks": task_by_day.get(day, 0),
            "completed_by_subject": subjects_by_day.get(day, []),
            "focus_sessions": int(session["sessions"]) if session else 0,
            "focus_minutes": int(session["minutes"]) if session else 0,
        })
    return {"start_date": start.isoformat(), "end_date": end.isoformat(), "days": points}
