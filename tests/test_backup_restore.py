from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.routes import create_app
from app.database.db import Database
from app.services.progress_service import get_progress
from app.services.study_session_service import create_study_session
from app.services.task_service import create_task, list_tasks, update_task


def test_backup_restore_adds_data_and_remaps_session_task_link(tmp_path):
    source = Database(tmp_path / "source.sqlite3")
    source.initialize()
    source_task = create_task(
        source,
        {
            "title": "Review control systems",
            "subject": "Electrical Engineering",
            "estimated_minutes": 45,
        },
    )
    started_at = datetime.now(UTC) - timedelta(minutes=25)
    create_study_session(
        source,
        {
            "task_id": source_task["id"],
            "subject": "Electrical Engineering",
            "duration_minutes": 25,
            "notes": "Review feedback loops",
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )
    backup = TestClient(create_app(source)).get("/api/exports/backup.json").json()

    target = Database(tmp_path / "target.sqlite3")
    target.initialize()
    create_task(target, {"title": "Keep this existing task"})
    client = TestClient(create_app(target))
    response = client.post("/api/imports/backup", json=backup)

    assert response.status_code == 200
    assert response.json() == {
        "status": "restored",
        "tasks_added": 1,
        "study_sessions_added": 1,
    }
    target_tasks = list_tasks(target, status="all", limit=10)
    assert {task["title"] for task in target_tasks} == {
        "Keep this existing task",
        "Review control systems",
    }
    history = client.get("/api/study-sessions").json()
    restored_session = history["items"][0]
    restored_task = next(
        task for task in target_tasks if task["title"] == "Review control systems"
    )
    assert restored_session["task_id"] == restored_task["id"]
    assert get_progress(target)["focus_sessions"] == 1


def test_backup_restore_rejects_invalid_schema_without_writing(tmp_path):
    database = Database(tmp_path / "restore.sqlite3")
    database.initialize()
    client = TestClient(create_app(database))

    response = client.post(
        "/api/imports/backup",
        json={"app": "Other", "schema_version": 1, "tasks": [], "study_sessions": []},
    )

    assert response.status_code == 422
    assert get_progress(database)["total_tasks"] == 0


def test_backup_restore_preserves_recurring_series_links(tmp_path):
    source = Database(tmp_path / "recurring-source.sqlite3")
    source.initialize()
    task = create_task(
        source,
        {
            "title": "Monthly review",
            "due_date": "2026-01-31",
            "recurrence_rule": "monthly",
            "recurrence_until": "2026-03-31",
        },
    )
    update_task(source, task["id"], {"completed": True})
    backup = TestClient(create_app(source)).get("/api/exports/backup.json").json()

    target = Database(tmp_path / "recurring-target.sqlite3")
    target.initialize()
    response = TestClient(create_app(target)).post("/api/imports/backup", json=backup)

    assert response.status_code == 200
    with target.session() as connection:
        rows = connection.execute(
            "SELECT id, due_date, recurrence_series_id FROM tasks ORDER BY due_date"
        ).fetchall()
    assert len(rows) == 2
    assert rows[0]["recurrence_series_id"] == rows[0]["id"]
    assert rows[1]["recurrence_series_id"] == rows[0]["id"]
