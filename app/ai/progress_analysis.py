"""AI-assisted analysis of task progress and next study steps."""

import json
from typing import Any

from app.ai.llm_client import complete_chat
from app.database.db import Database
from app.services.progress_service import get_progress_analysis_context


def analyze_progress(database: Database, *, user_id: int | None = None) -> dict[str, Any]:
    evidence = get_progress_analysis_context(database, user_id=user_id)
    system_prompt = (
        "You are StudyPilot, a careful academic study coach. Analyze only the "
        "database-derived progress evidence supplied by the user. Do not claim "
        "to have trained on the student, predict grades, or infer learning mastery "
        "from task completion alone. Distinguish observations from suggestions. "
        "If there is little or no activity, say that evidence is limited and "
        "recommend a concrete way to collect useful progress. Give practical, "
        "kind, specific actions across subjects where evidence supports them. "
        "Return only a valid JSON object with these fields: summary (string), "
        "strengths (array of strings), focus_areas (array of strings), "
        "recommendations (array of objects with title, reason, and action strings), "
        "next_step (string)."
    )
    response = complete_chat(
        system_prompt,
        "Analyze this StudyPilot evidence and make a short, evidence-grounded "
        "recommendation:\n" + json.dumps(evidence, ensure_ascii=False),
        json_mode=True,
    )
    try:
        result = json.loads(response)
    except json.JSONDecodeError as error:
        raise RuntimeError("AI provider returned invalid progress-analysis JSON.") from error

    required = {"summary", "strengths", "focus_areas", "recommendations", "next_step"}
    if not isinstance(result, dict) or not required.issubset(result):
        raise RuntimeError("AI provider response is missing progress-analysis fields.")
    for field in ("summary", "next_step"):
        if (
            not isinstance(result[field], str)
            or not result[field].strip()
            or len(result[field]) > 1500
        ):
            raise RuntimeError(f"AI provider returned an invalid {field} field.")
    for field in ("strengths", "focus_areas"):
        if not isinstance(result[field], list) or not all(
            isinstance(item, str) and item.strip() and len(item) <= 500
            for item in result[field]
        ) or len(result[field]) > 10:
            raise RuntimeError(f"AI provider returned invalid {field}.")
    recommendations = result["recommendations"]
    recommendation_fields = {"title", "reason", "action"}
    if not isinstance(recommendations, list) or not all(
        isinstance(item, dict)
        and recommendation_fields.issubset(item)
        and all(
            isinstance(item[field], str)
            and item[field].strip()
            and len(item[field]) <= 1000
            for field in recommendation_fields
        )
        for item in recommendations
    ) or len(recommendations) > 8:
        raise RuntimeError("AI provider returned invalid progress recommendations.")
    return {"analysis": result, "evidence": evidence}
