import json
from datetime import date

from fastapi.testclient import TestClient

from app.ai import progress_analysis
from app.api import routes
from app.database.db import Database
from app.services.progress_service import get_progress_analysis_context
from app.services.task_service import create_task, update_task


VALID_ANALYSIS = {
    "summary": "You have completed one of two tasks.",
    "strengths": ["You have completed a task in Biology."],
    "focus_areas": ["One Biology task is still open."],
    "recommendations": [
        {
            "title": "Schedule Biology review",
            "reason": "One task remains open in that subject.",
            "action": "Set aside 30 minutes to finish the review.",
        }
    ],
    "next_step": "Review the open Biology task.",
}


def test_progress_analysis_uses_bounded_aggregate_evidence(tmp_path, monkeypatch):
    database = Database(tmp_path / "progress-analysis.sqlite3")
    database.initialize()
    task = create_task(
        database,
        {
            "title": "Review cell structure",
            "subject": "Biology",
            "due_date": "2026-10-21",
            "estimated_minutes": 30,
        },
    )
    update_task(database, task["id"], {"completed": True})

    captured = {}

    def fake_complete(system_prompt, user_prompt, *, json_mode):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        captured["json_mode"] = json_mode
        return json.dumps(VALID_ANALYSIS)

    monkeypatch.setattr(progress_analysis, "complete_chat", fake_complete)
    result = progress_analysis.analyze_progress(database)

    assert result["analysis"] == VALID_ANALYSIS
    assert result["evidence"]["progress"]["completed_tasks"] == 1
    assert result["evidence"]["subject_progress"] == [
        {"subject": "Biology", "total": 1, "completed": 1}
    ]
    assert result["evidence"]["focus_sessions_in_last_30_days"] == 0
    assert "Review cell structure" not in captured["user"]
    assert "Do not claim" in captured["system"]
    assert captured["json_mode"] is True


def test_progress_context_bounds_subject_groups_and_reports_recent_activity(tmp_path):
    database = Database(tmp_path / "progress-context.sqlite3")
    database.initialize()
    for number in range(25):
        create_task(database, {"title": f"Task {number}", "subject": f"Subject {number}"})

    context = get_progress_analysis_context(database, today=date(2026, 10, 20))
    assert context["progress"]["total_tasks"] == 25
    assert len(context["subject_progress"]) == 20
    assert context["tasks_completed_in_last_30_days"] == 0
    assert "by_subject" not in context["progress"]


def test_progress_analysis_api_handles_missing_provider_and_success(tmp_path, monkeypatch):
    database = Database(tmp_path / "progress-api.sqlite3")
    client = TestClient(routes.create_app(database))

    def missing_provider(_database):
        raise routes.AIProviderNotConfigured("Configure the AI provider.")

    monkeypatch.setattr(
        routes,
        "analyze_progress",
        missing_provider,
    )
    assert client.post("/api/progress/analyze", json={}).status_code == 503

    monkeypatch.setattr(routes, "analyze_progress", lambda _database: VALID_ANALYSIS)
    response = client.post("/api/progress/analyze", json={})
    assert response.status_code == 200
    assert response.json() == VALID_ANALYSIS
