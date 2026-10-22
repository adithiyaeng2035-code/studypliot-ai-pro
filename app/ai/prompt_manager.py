"""Prompt construction for the optional OpenAI-compatible assistant."""


def study_assistant_prompt() -> str:
    return (
        "You are StudyPilot, a practical study-planning assistant. Be encouraging, "
        "specific, and concise. Use only the task and progress context provided; "
        "do not claim that a task was changed."
    )
