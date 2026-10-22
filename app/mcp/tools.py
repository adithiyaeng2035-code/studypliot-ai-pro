"""Reusable MCP tool implementations."""

from typing import Any

from app.config import AUTH_ENABLED, DATABASE_BACKEND, DATABASE_PATH, DATABASE_URL
from app.database.db import Database
from app.services.study_planner import create_study_plan
from app.services.task_service import count_tasks, create_task, list_tasks, update_task


def _database(database: Database | None) -> Database:
    if AUTH_ENABLED:
        raise RuntimeError(
            "MCP tools are disabled when account authentication is enabled; "
            "use the authenticated StudyPilot API instead."
        )
    target = DATABASE_URL or (
        "postgresql" if DATABASE_BACKEND == "postgresql" else DATABASE_PATH
    )
    result = database or Database(target)
    result.initialize()
    return result


def list_open_tasks(database: Database | None = None) -> dict[str, Any]:
    """Return the first 50 incomplete tasks and the total open task count."""
    active_database = _database(database)
    return {
        "items": list_tasks(active_database, status="open", limit=50),
        "total": count_tasks(active_database, status="open"),
        "page_size": 50,
    }


def add_study_task(
    title: str,
    subject: str = "General",
    due_date: str | None = None,
    estimated_minutes: int = 30,
    database: Database | None = None,
) -> dict[str, Any]:
    """Create a study task with an optional ISO-formatted due date."""
    return create_task(
        _database(database),
        {
            "title": title,
            "subject": subject,
            "due_date": due_date,
            "estimated_minutes": estimated_minutes,
        },
    )


def complete_study_task(task_id: int, database: Database | None = None) -> dict[str, Any]:
    """Mark a study task complete."""
    return update_task(_database(database), task_id, {"completed": True})


def get_study_plan(days: int = 7, database: Database | None = None) -> dict[str, Any]:
    """Return an upcoming study plan for open tasks."""
    return create_study_plan(_database(database), days=days)
