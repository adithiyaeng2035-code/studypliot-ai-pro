import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.ai import study_planning
from app.api import routes
from app.database.db import Database
from app.services.task_service import count_tasks


def make_database(tmp_path):
    database = Database(tmp_path / "study-plan.sqlite3")
    database.initialize()
    return database


def example_sessions(start: date, deadline: date):
    session_day = min(start + timedelta(days=1), deadline)
    return [
        {
            "date": session_day.isoformat(),
            "title": "Review semiconductor basics",
            "description": "Learn conductors, insulators, and band gaps.",
            "estimated_minutes": 30,
        }
    ]


def test_ai_plan_generation_returns_bounded_reviewable_draft(monkeypatch):
    today = date.today()
    deadline = today + timedelta(days=7)
    sessions = example_sessions(today, deadline)
    captured = {}

    def fake_complete(system_prompt, user_prompt, *, json_mode):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        captured["json_mode"] = json_mode
        return json.dumps({"sessions": sessions})

    monkeypatch.setattr(study_planning, "complete_chat", fake_complete)
    plan = study_planning.generate_study_plan(
        goal="Understand semiconductors",
        subject="Physics",
        deadline=deadline,
        level="High school",
        study_days_per_week=3,
        minutes_per_day=45,
        today=today,
    )

    assert plan["sessions"] == sessions
    assert plan["total_minutes"] == 30
    assert captured["json_mode"] is True
    assert "no more than one per date" in captured["system"]
    assert "Understand semiconductors" in captured["user"]


@pytest.mark.parametrize(
    "session_changes",
    [
        {"date": (date.today() - timedelta(days=1)).isoformat()},
        {"estimated_minutes": 46},
        {"title": ""},
    ],
)
def test_model_generated_plan_rejects_sessions_outside_constraints(
    monkeypatch, session_changes
):
    today = date.today()
    deadline = today + timedelta(days=7)
    session = example_sessions(today, deadline)[0] | session_changes
    monkeypatch.setattr(
        study_planning,
        "complete_chat",
        lambda *_args, **_kwargs: json.dumps({"sessions": [session]}),
    )

    with pytest.raises(RuntimeError):
        study_planning.generate_study_plan(
            goal="Study physics",
            subject="Physics",
            deadline=deadline,
            level="",
            study_days_per_week=3,
            minutes_per_day=45,
            today=today,
        )


def test_plan_approval_endpoint_only_writes_after_approval(tmp_path, monkeypatch):
    database = make_database(tmp_path)
    today = date.today()
    deadline = today + timedelta(days=7)
    plan = {
        "goal": "Understand semiconductors",
        "subject": "Physics",
        "start_date": today.isoformat(),
        "deadline": deadline.isoformat(),
        "study_days_per_week": 3,
        "minutes_per_day": 45,
        "sessions": example_sessions(today, deadline),
        "total_minutes": 30,
    }
    monkeypatch.setattr(routes, "generate_study_plan", lambda **_kwargs: plan)
    client = TestClient(routes.create_app(database))

    generated = client.post(
        "/api/plans/generate",
        json={
            "goal": plan["goal"],
            "subject": plan["subject"],
            "deadline": plan["deadline"],
            "level": "High school",
            "study_days_per_week": 3,
            "minutes_per_day": 45,
        },
    )
    assert generated.status_code == 200
    assert generated.json() == plan
    assert count_tasks(database) == 0

    approved = client.post("/api/plans/approve", json=generated.json())
    assert approved.status_code == 201
    assert approved.json()["created_count"] == 1
    assert approved.json()["tasks"][0]["subject"] == "Physics"
    assert approved.json()["tasks"][0]["due_date"] == plan["sessions"][0]["date"]
    assert count_tasks(database) == 1


def test_plan_generation_reports_missing_ai_provider(tmp_path):
    database = make_database(tmp_path)
    client = TestClient(routes.create_app(database))
    response = client.post(
        "/api/plans/generate",
        json={
            "goal": "Study physics",
            "subject": "Physics",
            "deadline": (date.today() + timedelta(days=7)).isoformat(),
        },
    )
    assert response.status_code == 503
    assert "LLM_BASE_URL" in response.json()["detail"]


def test_approval_revalidates_untrusted_plan_content(tmp_path):
    database = make_database(tmp_path)
    today = date.today()
    deadline = today + timedelta(days=7)
    session = example_sessions(today, deadline)[0]
    session["date"] = (today - timedelta(days=1)).isoformat()
    client = TestClient(routes.create_app(database))

    response = client.post(
        "/api/plans/approve",
        json={
            "goal": "Study physics",
            "subject": "Physics",
            "start_date": today.isoformat(),
            "deadline": deadline.isoformat(),
            "study_days_per_week": 3,
            "minutes_per_day": 45,
            "sessions": [session],
        },
    )
    assert response.status_code == 400
    assert count_tasks(database) == 0
