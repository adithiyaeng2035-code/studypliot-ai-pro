from datetime import UTC, date, datetime

from app.database.db import Database
from app.services.calendar_service import get_calendar_events
from app.services.study_session_service import create_study_session
from app.services.task_service import create_task


def test_calendar_returns_due_tasks_and_sessions_for_owner_and_date_range(tmp_path):
    database = Database(tmp_path / "calendar.sqlite3")
    database.initialize()
    with database.session() as connection:
        first_user = connection.execute(
            "INSERT INTO users (email, full_name, password_hash, created_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            ("one@example.edu", "One", "hash", "2026-10-01T00:00:00+00:00"),
        ).fetchone()["id"]
        second_user = connection.execute(
            "INSERT INTO users (email, full_name, password_hash, created_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            ("two@example.edu", "Two", "hash", "2026-10-01T00:00:00+00:00"),
        ).fetchone()["id"]

    first_task = create_task(
        database, {"title": "Owner task", "due_date": "2026-10-20"}, user_id=first_user
    )
    create_task(
        database, {"title": "Other account task", "due_date": "2026-10-20"}, user_id=second_user
    )
    create_task(
        database, {"title": "Out of range task", "due_date": "2026-11-20"}, user_id=first_user
    )
    create_study_session(
        database,
        {
            "task_id": first_task["id"],
            "subject": "Physics",
            "duration_minutes": 25,
            "notes": "",
            "started_at": datetime(2026, 10, 20, 9, tzinfo=UTC).isoformat(),
            "completed_at": datetime(2026, 10, 20, 9, 25, tzinfo=UTC).isoformat(),
        },
        user_id=first_user,
    )

    calendar = get_calendar_events(
        database, start=date(2026, 10, 19), days=7, user_id=first_user
    )

    assert [task["title"] for task in calendar["tasks"]] == ["Owner task"]
    assert calendar["study_sessions"][0]["subject"] == "Physics"
    assert calendar["study_sessions"][0]["task_title"] == "Owner task"
