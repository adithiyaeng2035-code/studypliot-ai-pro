"""Study assistant orchestration."""

from app.ai.llm_client import complete_chat, is_configured
from app.ai.prompt_manager import study_assistant_prompt
from app.database.db import Database
from app.services.progress_service import get_progress
from app.services.task_service import list_tasks


def answer_question(
    database: Database, question: str, *, user_id: int | None = None
) -> dict[str, str | bool]:
    prompt = question.strip()
    if not prompt:
        raise ValueError("message is required")
    tasks = list_tasks(database, status="open", user_id=user_id)
    progress = get_progress(database, user_id=user_id)
    context = (
        f"Open tasks: {tasks[:20]}\n"
        f"Progress: {progress}\n"
        f"Student question: {prompt}"
    )
    if is_configured():
        return {
            "reply": complete_chat(study_assistant_prompt(), context),
            "ai_enabled": True,
        }
    if not tasks:
        reply = (
            "You have no open tasks right now. Add an assignment with its subject and "
            "due date, and I can help you plan your next study session."
        )
    else:
        next_task = tasks[0]
        due = f", due {next_task['due_date']}" if next_task["due_date"] else ""
        reply = (
            f"You have {progress['open_tasks']} open task(s). A good next step is "
            f"“{next_task['title']}” for {next_task['subject']}{due} "
            f"(about {next_task['estimated_minutes']} minutes). "
            "Add an AI provider in the environment settings for conversational answers."
        )
    return {"reply": reply, "ai_enabled": False}
