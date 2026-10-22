from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.routes import create_app
from app.database.db import Database
from app.services.progress_service import get_progress_analysis_context
from app.services.study_session_service import (
    create_study_session,
    get_focus_time_analysis,
    list_study_sessions,
)
from app.services.task_service import create_task, delete_task


def make_database(tmp_path):
    database = Database(tmp_path / "study-sessions.sqlite3")
    database.initialize()
    return database


def make_session_values(**overrides):
    started_at = datetime.now(UTC) - timedelta(minutes=25)
    values = {
        "subject": "Physics",
        "duration_minutes": 25,
        "notes": "Review semiconductors",
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    values.update(overrides)
    return values


def test_study_session_is_persisted_with_optional_task_link(tmp_path):
    database = make_database(tmp_path)
    task = create_task(database, {"title": "Semiconductor notes", "subject": "Physics"})

    session = create_study_session(
        database, make_session_values(task_id=task["id"])
    )
    history = list_study_sessions(database)

    assert session["task_id"] == task["id"]
    assert session["task_title"] == "Semiconductor notes"
    assert session["subject"] == "Physics"
    assert session["duration_minutes"] == 25
    assert history["total_sessions"] == 1
    assert history["total_minutes"] == 25
    assert history["items"][0]["id"] == session["id"]


def test_study_session_history_survives_linked_task_deletion(tmp_path):
    database = make_database(tmp_path)
    task = create_task(database, {"title": "Review", "subject": "Math"})
    session = create_study_session(
        database,
        make_session_values(task_id=task["id"], subject="Math"),
    )

    delete_task(database, task["id"])
    saved = list_study_sessions(database)["items"][0]

    assert saved["id"] == session["id"]
    assert saved["task_id"] is None
    assert saved["task_title"] is None
    assert saved["subject"] == "Math"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"duration_minutes": 0}, "duration_minutes"),
        ({"task_id": 999}, "task_id"),
        ({"started_at": "not-a-datetime"}, "ISO datetimes"),
    ],
)
def test_study_session_rejects_invalid_values(tmp_path, overrides, message):
    with pytest.raises(ValueError, match=message):
        create_study_session(make_database(tmp_path), make_session_values(**overrides))


def test_study_session_requires_timezone_and_positive_elapsed_time(tmp_path):
    database = make_database(tmp_path)
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="include a timezone"):
        create_study_session(
            database,
            make_session_values(started_at=now.replace(tzinfo=None).isoformat()),
        )
    with pytest.raises(ValueError, match="after started_at"):
        create_study_session(
            database,
            make_session_values(
                started_at=now.isoformat(),
                completed_at=(now - timedelta(seconds=1)).isoformat(),
            ),
        )


def test_study_session_api_validation_history_and_progress_context(tmp_path):
    database = make_database(tmp_path)
    client = TestClient(create_app(database))
    values = make_session_values()

    assert "Study session timer" in client.get("/").text
    created = client.post("/api/study-sessions", json=values)
    assert created.status_code == 201
    assert created.json()["subject"] == "Physics"
    assert client.get("/api/study-sessions?limit=1").json()["total_minutes"] == 25
    assert client.get("/api/study-sessions?limit=101").status_code == 422
    assert client.post(
        "/api/study-sessions",
        json={**values, "duration_minutes": 241},
    ).status_code == 422
    assert get_progress_analysis_context(database)["focus_sessions_in_last_30_days"] == 1
    assert get_progress_analysis_context(database)["focus_minutes_in_last_30_days"] == 25


def test_focus_time_analysis_returns_recent_daily_subject_and_streak_totals(tmp_path):
    database = make_database(tmp_path)
    today = date(2026, 10, 22)

    def save(day, subject, minutes):
        completed = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=10)
        create_study_session(
            database,
            make_session_values(
                subject=subject,
                duration_minutes=minutes,
                started_at=(completed - timedelta(minutes=minutes)).isoformat(),
                completed_at=completed.isoformat(),
            ),
        )

    save(today - timedelta(days=1), "Mathematics", 35)
    save(today, "Physics", 25)
    save(today - timedelta(days=10), "Mathematics", 30)

    result = get_focus_time_analysis(database, today=today)

    assert result["last_7_days"]["minutes"] == 60
    assert result["last_7_days"]["sessions"] == 2
    assert result["last_30_days"]["minutes"] == 90
    assert result["last_30_days"]["active_days"] == 3
    assert result["last_30_days"]["current_streak_days"] == 2
    assert result["last_30_days"]["by_subject"] == [
        {"subject": "Mathematics", "sessions": 2, "minutes": 65},
        {"subject": "Physics", "sessions": 1, "minutes": 25},
    ]
