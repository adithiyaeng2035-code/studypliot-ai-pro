import pytest
from fastapi.testclient import TestClient

from app.api.routes import create_app
from app.database.db import Database
from app.services.progress_service import get_progress
from app.services.task_service import create_task, delete_task, list_tasks, update_task


def new_database(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    return database


def test_task_lifecycle_and_progress(tmp_path):
    database = new_database(tmp_path)
    task = create_task(
        database,
        {
            "title": "  Read chapter  ",
            "subject": " Biology ",
            "due_date": "2026-10-25",
            "estimated_minutes": 45,
        },
    )

    assert task["title"] == "Read chapter"
    assert task["subject"] == "Biology"
    assert task["completed"] is False
    assert list_tasks(database, status="open") == [task]

    completed = update_task(database, task["id"], {"completed": True})
    assert completed["completed"] is True
    assert completed["completed_at"]
    assert get_progress(database) == {
        "total_tasks": 1,
        "completed_tasks": 1,
        "open_tasks": 0,
        "completion_percent": 100,
        "completed_minutes": 45,
        "focus_sessions": 0,
        "focus_minutes": 0,
        "by_subject": [{"subject": "Biology", "total": 1, "completed": 1}],
    }

    update_task(database, task["id"], {"completed": False, "due_date": None})
    assert list_tasks(database, status="open")[0]["due_date"] is None
    delete_task(database, task["id"])
    assert list_tasks(database) == []


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"title": " "}, "title is required"),
        ({"title": "task", "estimated_minutes": 0}, "estimated_minutes"),
        ({"title": "task", "due_date": "not-a-date"}, "due_date"),
    ],
)
def test_create_rejects_invalid_values(tmp_path, values, message):
    with pytest.raises(ValueError, match=message):
        create_task(new_database(tmp_path), values)


def test_update_rejects_null_required_fields_and_missing_task(tmp_path):
    database = new_database(tmp_path)
    task = create_task(database, {"title": "Review"})
    with pytest.raises(ValueError, match="title cannot be null"):
        update_task(database, task["id"], {"title": None})
    with pytest.raises(KeyError, match="was not found"):
        delete_task(database, 900)


def test_api_serves_ui_and_validates_task_requests(tmp_path):
    client = TestClient(create_app(new_database(tmp_path)))

    assert client.get("/").status_code == 200
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["database"] == "ok"
    assert health["ai_provider"] in {"configured", "not_configured"}
    response = client.post(
        "/api/tasks",
        json={"title": "Practice algebra", "subject": "Math", "estimated_minutes": 20},
    )
    assert response.status_code == 201
    task_id = response.json()["id"]
    task_page = client.get("/api/tasks?status=open").json()
    assert task_page["items"][0]["id"] == task_id
    assert task_page["total"] == 1
    assert client.patch(f"/api/tasks/{task_id}", json={"completed": True}).json()["completed"]
    assert client.get("/api/progress").json()["completed_minutes"] == 20
    assert client.patch("/api/tasks/999", json={"completed": True}).status_code == 404
    assert client.post("/api/tasks", json={"title": "Invalid", "estimated_minutes": 0}).status_code == 422
    assert client.delete(f"/api/tasks/{task_id}").status_code == 204


def test_deadline_endpoint_accepts_bounded_window(tmp_path):
    client = TestClient(create_app(new_database(tmp_path)))
    response = client.get("/api/deadlines?days=91")
    assert response.status_code == 422


def test_task_api_paginates_50000_rows(tmp_path):
    database = new_database(tmp_path)
    connection = database.connect()
    try:
        connection.executemany(
            """INSERT INTO tasks
               (title, subject, description, due_date, estimated_minutes, completed, created_at)
               VALUES (?, ?, '', ?, 30, 0, '2026-10-20T00:00:00+00:00')""",
            (
                (f"Task {number}", "General", f"2026-10-{(number % 28) + 1:02}")
                for number in range(50_000)
            ),
        )
        connection.commit()
    finally:
        connection.close()

    client = TestClient(create_app(database))
    first_page = client.get("/api/tasks?page=1&page_size=50").json()
    last_page = client.get("/api/tasks?page=1000&page_size=50").json()
    clamped_page = client.get("/api/tasks?page=1001&page_size=50").json()

    assert first_page["total"] == 50_000
    assert first_page["pages"] == 1_000
    assert first_page["page"] == 1
    assert len(first_page["items"]) == 50
    assert last_page["page"] == 1_000
    assert len(last_page["items"]) == 50
    assert clamped_page["page"] == 1_000
    assert len(clamped_page["items"]) == 50
    assert client.get("/api/tasks?page_size=101").status_code == 422
