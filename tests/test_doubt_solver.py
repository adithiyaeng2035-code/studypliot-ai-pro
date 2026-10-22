import json

import pytest
from fastapi.testclient import TestClient

from app.ai import doubt_solver
from app.api import routes
from app.database.db import Database


VALID_RESULT = {
    "answer": "Acceleration is the rate of change of velocity.",
    "steps": ["Compare initial and final velocity.", "Divide the change by elapsed time."],
    "concepts": ["velocity", "time"],
    "analysis": "The question is about distinguishing speed from acceleration.",
    "difficulty": "beginner",
    "misconception": "Acceleration is not the same as velocity.",
    "follow_up": "What is the acceleration if velocity stays constant?",
}


def test_solver_returns_structured_explanation(monkeypatch):
    captured = {}

    def fake_complete(system_prompt, user_prompt, *, json_mode):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        captured["json_mode"] = json_mode
        return json.dumps(VALID_RESULT)

    monkeypatch.setattr(doubt_solver, "complete_chat", fake_complete)
    result = doubt_solver.solve_doubt(
        subject=" Physics ",
        question="What is acceleration?",
        level="High school",
        context="I confuse it with velocity.",
    )

    assert result == VALID_RESULT
    assert captured["json_mode"] is True
    assert "Subject: Physics" in captured["user"]
    assert "I confuse it with velocity." in captured["user"]
    assert "untrusted student content" in captured["system"]


def test_solver_rejects_malformed_provider_response(monkeypatch):
    monkeypatch.setattr(
        doubt_solver,
        "complete_chat",
        lambda *_args, **_kwargs: '{"answer":"incomplete"}',
    )

    with pytest.raises(RuntimeError, match="missing doubt-analysis fields"):
        doubt_solver.solve_doubt(subject="Physics", question="Explain acceleration.")


def test_doubt_api_reports_missing_ai_configuration(tmp_path, monkeypatch):
    database = Database(tmp_path / "doubt.sqlite3")
    monkeypatch.setattr(routes, "is_configured", lambda: False)
    client = TestClient(routes.create_app(database))

    assert client.get("/api/ai/status").json() == {"configured": False}
    response = client.post(
        "/api/doubts/solve",
        json={"subject": "Physics", "question": "Explain acceleration."},
    )
    assert response.status_code == 503
    assert "LLM_BASE_URL" in response.json()["detail"]


def test_doubt_api_returns_structured_provider_result(tmp_path, monkeypatch):
    database = Database(tmp_path / "doubt-api.sqlite3")
    monkeypatch.setattr(routes, "solve_doubt", lambda **_kwargs: VALID_RESULT)
    client = TestClient(routes.create_app(database))

    response = client.post(
        "/api/doubts/solve",
        json={"subject": "Math", "question": "Why does this equation work?"},
    )
    assert response.status_code == 200
    assert response.json() == VALID_RESULT
    assert client.get("/doubts.html").status_code == 200


def test_doubt_api_validates_required_fields(tmp_path):
    database = Database(tmp_path / "doubt-validation.sqlite3")
    client = TestClient(routes.create_app(database))
    response = client.post("/api/doubts/solve", json={"subject": "", "question": ""})
    assert response.status_code == 422
