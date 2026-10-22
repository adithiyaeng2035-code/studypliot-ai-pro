from fastapi.testclient import TestClient

from app.ai import assistant
from app.api import routes
from app.database.db import Database


def test_tutor_chat_uses_bounded_conversation_context(monkeypatch):
    captured = {}
    monkeypatch.setattr(assistant, "is_configured", lambda: True)

    def fake_complete(system_prompt, user_prompt):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "Let's work it through step by step."

    monkeypatch.setattr(assistant, "complete_chat", fake_complete)
    history = [
        {"role": "user", "content": "What is velocity?"},
        {"role": "assistant", "content": "Change in position over time."},
    ]
    result = assistant.tutor_chat("How is that different from speed?", history, "learn")

    assert result == {"reply": "Let's work it through step by step.", "ai_enabled": True}
    assert "Student: What is velocity?" in captured["user"]
    assert "StudyPilot: Change in position over time." in captured["user"]
    assert "Student: How is that different from speed?" in captured["user"]
    assert "versatile, friendly AI assistant" in captured["system"]
    assert "Selected help mode: learn" in captured["system"]


def test_tutor_chat_api_validates_history_and_returns_local_setup_message(tmp_path, monkeypatch):
    database = Database(tmp_path / "tutor.sqlite3")
    monkeypatch.setattr(assistant, "is_configured", lambda: False)
    client = TestClient(routes.create_app(database))

    response = client.post("/api/tutor/chat", json={"message": "Explain fractions"})
    assert response.status_code == 200
    assert response.json()["ai_enabled"] is False
    assert "LLM_BASE_URL" in response.json()["reply"]
    assert client.get("/tutor.html").status_code == 200

    too_many_turns = [{"role": "user", "content": "Question"}] * 9
    invalid = client.post(
        "/api/tutor/chat",
        json={"message": "Explain fractions", "history": too_many_turns},
    )
    assert invalid.status_code == 422


def test_time_coach_receives_saved_focus_summary_and_course_standard(tmp_path, monkeypatch):
    database = Database(tmp_path / "tutor-time-coach.sqlite3")
    captured = {}
    focus = {"last_7_days": {"minutes": 90, "sessions": 3}}
    monkeypatch.setattr(assistant, "is_configured", lambda: True)
    monkeypatch.setattr(routes, "is_configured", lambda: True)
    monkeypatch.setattr(routes, "get_focus_time_analysis", lambda *_args, **_kwargs: focus)

    def fake_complete(_system, user_prompt):
        captured["prompt"] = user_prompt
        return "Your recent study sessions total 90 minutes."

    monkeypatch.setattr(assistant, "complete_chat", fake_complete)
    client = TestClient(routes.create_app(database))
    response = client.post(
        "/api/tutor/chat",
        json={
            "message": "Analyze my consistency.",
            "mode": "time_coach",
            "study_context": "Grade 12, CBSE Physics",
        },
    )

    assert response.status_code == 200
    assert "90" in captured["prompt"]
    assert "Grade 12, CBSE Physics" in captured["prompt"]
    assert "untrusted context" in captured["prompt"]


def test_industry_mode_uses_requested_sector_and_region(monkeypatch):
    captured = {}
    monkeypatch.setattr(assistant, "is_configured", lambda: True)

    def fake_complete(system_prompt, user_prompt):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "Here is an industry example."

    monkeypatch.setattr(assistant, "complete_chat", fake_complete)
    result = assistant.tutor_chat(
        "How is circuit analysis used at work?",
        [],
        "industry",
        "Electrical engineering, renewable energy, India",
    )

    assert result["ai_enabled"] is True
    assert "industry work" in captured["system"]
    assert "renewable energy, India" in captured["user"]
