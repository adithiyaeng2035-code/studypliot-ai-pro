from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api import routes
from app.database.db import Database
from app.services import auth_service
from app.services.task_service import create_task


def test_hosted_accounts_isolate_tasks_and_protect_mutations(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "AUTH_ENABLED", True)
    monkeypatch.setattr(routes, "AUTH_COOKIE_SECURE", False)
    monkeypatch.setattr(auth_service, "AUTH_ALLOW_REGISTRATION", True)

    database = Database(tmp_path / "accounts.sqlite3")
    database.initialize()
    legacy_task = create_task(database, {"title": "Existing local study task"})
    app = routes.create_app(database)
    first = TestClient(app)

    registration = first.post(
        "/api/auth/register",
        json={
            "email": "student-one@example.edu",
            "password": "correct-horse-battery-staple",
            "full_name": "Student One",
        },
    )
    assert registration.status_code == 201
    assert registration.json()["user"]["full_name"] == "Student One"
    csrf = registration.json()["csrf_token"]
    assert registration.headers["set-cookie"].lower().find("httponly") >= 0
    assert first.get("/api/tasks").json()["total"] == 1
    assert first.get("/api/tasks").json()["items"][0]["id"] == legacy_task["id"]
    assert first.get("/api/auth/me").json()["user"]["full_name"] == "Student One"
    signed_in = first.post(
        "/api/auth/login",
        json={"email": "student-one@example.edu", "password": "correct-horse-battery-staple"},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["full_name"] == "Student One"
    csrf = signed_in.json()["csrf_token"]

    created = first.post(
        "/api/tasks",
        headers={"X-CSRF-Token": csrf},
        json={"title": "Private task"},
    )
    assert created.status_code == 201
    started = datetime.now(UTC) - timedelta(minutes=20)
    first_session = first.post(
        "/api/study-sessions",
        headers={"X-CSRF-Token": csrf},
        json={
            "task_id": created.json()["id"],
            "subject": "General",
            "duration_minutes": 20,
            "notes": "Private session",
            "started_at": started.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )
    assert first_session.status_code == 201
    assert first.get("/api/progress").json()["focus_sessions"] == 1

    second = TestClient(app)
    second_registration = second.post(
        "/api/auth/register",
        json={
            "email": "student-two@example.edu",
            "password": "another-correct-horse-battery",
            "full_name": "Student Two",
        },
    )
    assert second_registration.status_code == 201
    assert second.get("/api/tasks").json()["total"] == 0
    assert second.get("/api/progress").json()["focus_sessions"] == 0
    assert second.get("/api/study-sessions").json()["total_sessions"] == 0
    assert second.get("/api/exports/backup.json").json()["tasks"] == []
    assert second.get("/api/plan").json()["total_minutes"] == 0
    assert second.patch(
        f"/api/tasks/{created.json()['id']}", json={"completed": True}
    ).status_code == 403
    assert second.patch(
        f"/api/tasks/{created.json()['id']}",
        headers={"X-CSRF-Token": second_registration.json()["csrf_token"]},
        json={"completed": True},
    ).status_code == 404

    second_csrf = second_registration.json()["csrf_token"]
    second_task = second.post(
        "/api/tasks", headers={"X-CSRF-Token": second_csrf},
        json={"title": "Second account data"},
    )
    assert second_task.status_code == 201
    assert second.request(
        "DELETE", "/api/auth/account", headers={"X-CSRF-Token": second_csrf},
        json={"password": "incorrect-password"},
    ).status_code == 403
    deleted = second.request(
        "DELETE", "/api/auth/account", headers={"X-CSRF-Token": second_csrf},
        json={"password": "another-correct-horse-battery"},
    )
    assert deleted.status_code == 204
    assert second.get("/api/auth/me").json()["authenticated"] is False
    assert first.get("/api/tasks").json()["total"] == 2


def test_hosted_auth_redirects_pages_and_registration_needs_no_setup_token(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "AUTH_ENABLED", True)
    monkeypatch.setattr(routes, "AUTH_COOKIE_SECURE", False)
    monkeypatch.setattr(auth_service, "AUTH_ALLOW_REGISTRATION", True)

    database = Database(tmp_path / "auth-bootstrap.sqlite3")
    database.initialize()
    client = TestClient(routes.create_app(database))

    page = client.get("/", follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"] == "/login.html"
    response = client.post(
        "/api/auth/register",
        json={"email": "student@example.edu", "password": "long-enough-password", "full_name": "First Student"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["full_name"] == "First Student"


def test_registration_requires_a_student_name(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "AUTH_ENABLED", True)
    database = Database(tmp_path / "auth-name-required.sqlite3")
    client = TestClient(routes.create_app(database))

    response = client.post(
        "/api/auth/register",
        json={"email": "student@example.edu", "password": "long-enough-password"},
    )
    assert response.status_code == 422


def test_registration_can_be_closed_before_first_account(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_service, "AUTH_ALLOW_REGISTRATION", False)
    database = Database(tmp_path / "auth-registration-closed.sqlite3")
    client = TestClient(routes.create_app(database))

    response = client.post(
        "/api/auth/register",
        json={
            "email": "student@example.edu",
            "password": "long-enough-password",
            "full_name": "Student Name",
        },
    )
    assert response.status_code == 403
    assert "registration is disabled" in response.json()["detail"]

