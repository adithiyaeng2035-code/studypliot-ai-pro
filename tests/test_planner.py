from datetime import date

import pytest

from app.database.db import Database
from app.services.deadline_service import get_deadlines
from app.services.study_planner import create_study_plan
from app.services.task_service import create_task


def test_plan_groups_due_tasks_and_lists_later_tasks(tmp_path):
    database = Database(tmp_path / "planner.sqlite3")
    database.initialize()
    create_task(database, {"title": "Overdue quiz", "due_date": "2026-10-19", "estimated_minutes": 20})
    create_task(database, {"title": "Essay", "due_date": "2026-10-22", "estimated_minutes": 60})
    create_task(database, {"title": "No deadline", "estimated_minutes": 30})
    create_task(database, {"title": "Later project", "due_date": "2026-11-05", "estimated_minutes": 90})

    plan = create_study_plan(database, days=7, today=date(2026, 10, 20))
    assert plan["start_date"] == "2026-10-20"
    assert plan["end_date"] == "2026-10-26"
    assert plan["total_minutes"] == 110
    by_date = {session["date"]: session["tasks"] for session in plan["sessions"]}
    assert {task["title"] for task in by_date["2026-10-20"]} == {"Overdue quiz", "No deadline"}
    assert [task["title"] for task in by_date["2026-10-22"]] == ["Essay"]
    assert plan["unscheduled_count"] == 1

    deadlines = get_deadlines(database, today=date(2026, 10, 20), days=7)
    assert [task["title"] for task in deadlines["overdue"]] == ["Overdue quiz"]
    assert [task["title"] for task in deadlines["upcoming"]] == ["Essay"]


def test_plan_enforces_day_limit(tmp_path):
    database = Database(tmp_path / "planner.sqlite3")
    database.initialize()
    with pytest.raises(ValueError, match="days must be between 1 and 30"):
        create_study_plan(database, days=31, today=date(2026, 10, 20))


def test_plan_and_deadlines_bound_large_same_day_results(tmp_path):
    database = Database(tmp_path / "large-plan.sqlite3")
    database.initialize()
    for number in range(80):
        create_task(
            database,
            {
                "title": f"Task {number}",
                "due_date": "2026-10-22",
                "estimated_minutes": 10,
            },
        )

    plan = create_study_plan(database, days=7, today=date(2026, 10, 20))
    session = next(item for item in plan["sessions"] if item["date"] == "2026-10-22")
    assert len(session["tasks"]) == 25
    assert session["task_count"] == 80
    assert session["total_minutes"] == 800

    deadlines = get_deadlines(database, today=date(2026, 10, 20), limit=5)
    assert len(deadlines["upcoming"]) == 5
    assert deadlines["upcoming_count"] == 80
