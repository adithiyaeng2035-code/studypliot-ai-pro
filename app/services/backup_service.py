"""Validated, additive restoration of StudyPilot JSON backups."""

from datetime import datetime
from typing import Any

from app.database.db import Database


def _require_timestamp(value: str, field: str) -> str:
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO datetime") from error
    if timestamp.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return timestamp.isoformat()


def restore_backup(
    database: Database, backup: dict[str, Any], *, user_id: int | None = None
) -> dict[str, int]:
    """Add records from a validated backup without replacing existing records."""
    tasks = backup["tasks"]
    sessions = backup["study_sessions"]
    task_ids = [task["id"] for task in tasks]
    session_ids = [session["id"] for session in sessions]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("backup contains duplicate task IDs")
    if len(session_ids) != len(set(session_ids)):
        raise ValueError("backup contains duplicate study-session IDs")

    task_id_map: dict[int, int] = {}
    with database.session() as connection:
        for task in tasks:
            title = task["title"].strip()
            if not title:
                raise ValueError("task title cannot be empty")
            created_at = _require_timestamp(task["created_at"], "task created_at")
            completed_at = task["completed_at"]
            if completed_at is not None:
                completed_at = _require_timestamp(completed_at, "task completed_at")
            due_date = task["due_date"]
            if due_date is not None:
                due_date = due_date.isoformat()
            values = (
                title,
                task["subject"].strip() or "General",
                task["description"],
                due_date,
                task["estimated_minutes"],
                int(task["completed"]),
                created_at,
                completed_at,
            )
            sql = """INSERT INTO tasks
                     (title, subject, description, due_date, estimated_minutes,
                      completed, created_at, completed_at, recurrence_rule,
                      recurrence_until, recurrence_series_id, user_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)"""
            recurrence_rule = task.get("recurrence_rule", "none")
            recurrence_until = task.get("recurrence_until")
            if recurrence_until is not None:
                recurrence_until = recurrence_until.isoformat()
            if recurrence_rule != "none":
                if due_date is None or recurrence_until is None or recurrence_until < due_date:
                    raise ValueError("recurring task has invalid recurrence dates")
            elif recurrence_until is not None:
                raise ValueError("non-recurring task cannot have a repeat through date")
            values = (*values, recurrence_rule, recurrence_until)
            values = (*values, user_id)
            if database.is_postgres:
                new_id = connection.execute(sql + " RETURNING id", values).fetchone()["id"]
            else:
                new_id = connection.execute(sql, values).lastrowid
            task_id_map[task["id"]] = int(new_id)

        for task in tasks:
            series_id = task.get("recurrence_series_id")
            if task.get("recurrence_rule", "none") != "none" and series_id is None:
                series_id = task["id"]
            if series_id is not None:
                if series_id not in task_id_map:
                    raise ValueError("recurring task references a missing series task")
                connection.execute(
                    "UPDATE tasks SET recurrence_series_id = ? WHERE id = ?",
                    (task_id_map[series_id], task_id_map[task["id"]]),
                )

        for session in sessions:
            started_at = _require_timestamp(session["started_at"], "session started_at")
            completed_at = _require_timestamp(session["completed_at"], "session completed_at")
            if datetime.fromisoformat(completed_at) <= datetime.fromisoformat(started_at):
                raise ValueError("session completed_at must be after started_at")
            source_task_id = session["task_id"]
            if source_task_id is not None and source_task_id not in task_id_map:
                raise ValueError("study session references a task missing from the backup")
            values = (
                task_id_map.get(source_task_id),
                session["subject"].strip() or "General",
                session["duration_minutes"],
                session["notes"],
                started_at,
                completed_at,
                _require_timestamp(session["created_at"], "session created_at"),
            )
            sql = """INSERT INTO study_sessions
                     (task_id, subject, duration_minutes, notes, started_at, completed_at, created_at, user_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
            values = (*values, user_id)
            connection.execute(sql, values)

    return {"tasks_added": len(tasks), "study_sessions_added": len(sessions)}
