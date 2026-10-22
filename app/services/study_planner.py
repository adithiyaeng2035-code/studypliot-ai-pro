"""Rule-based study plan generation."""

from datetime import date, timedelta
from typing import Any

from app.database.db import Database

TASKS_PER_DAY_LIMIT = 25


def create_study_plan(
    database: Database, *, days: int = 7, today: date | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    if not 1 <= days <= 30:
        raise ValueError("days must be between 1 and 30")
    start = today or date.today()
    end = start + timedelta(days=days - 1)
    owner_filter = " AND user_id = ?" if user_id is not None else ""
    owner_parameters = (user_id,) if user_id is not None else ()
    with database.session() as connection:
        rows_query = """WITH candidates AS (
                   SELECT id, title, subject, due_date, estimated_minutes,
                          CASE WHEN due_date IS NULL OR due_date < ? THEN ? ELSE due_date END AS plan_date
                   FROM tasks
                   WHERE completed = 0 AND (due_date IS NULL OR due_date <= ?)"""
        rows_query += owner_filter + """),
               ranked AS (
                   SELECT *,
                          ROW_NUMBER() OVER (
                              PARTITION BY plan_date
                              ORDER BY CASE WHEN due_date IS NULL THEN 0 ELSE 1 END,
                                       due_date ASC, id ASC
                          ) AS task_rank,
                          COUNT(*) OVER (PARTITION BY plan_date) AS task_count,
                          SUM(estimated_minutes) OVER (PARTITION BY plan_date) AS total_minutes
                   FROM candidates
               )
               SELECT id, title, subject, due_date, estimated_minutes,
                      plan_date, task_rank, task_count, total_minutes
               FROM ranked
               WHERE task_rank <= ?
               ORDER BY plan_date, task_rank"""
        rows = connection.execute(
            rows_query,
            (start.isoformat(), start.isoformat(), end.isoformat(), *owner_parameters, TASKS_PER_DAY_LIMIT),
        ).fetchall()
        unscheduled_count = connection.execute(
            """SELECT COUNT(*) AS total FROM tasks
               WHERE completed = 0 AND due_date > ?""" + owner_filter,
            (end.isoformat(), *owner_parameters),
        ).fetchone()["total"]

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        task = dict(row)
        day = task.pop("plan_date")
        task.pop("task_rank")
        entry = grouped.setdefault(
            day,
            {
                "date": day,
                "tasks": [],
                "task_count": task.pop("task_count"),
                "total_minutes": task.pop("total_minutes"),
            },
        )
        entry["tasks"].append(task)

    for offset in range(days):
        day = (start + timedelta(days=offset)).isoformat()
        grouped.setdefault(
            day, {"date": day, "tasks": [], "task_count": 0, "total_minutes": 0}
        )
    sessions = [grouped[day] for day in sorted(grouped)]
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "sessions": sessions,
        "unscheduled_count": unscheduled_count,
        "total_minutes": sum(session["total_minutes"] for session in sessions),
    }
