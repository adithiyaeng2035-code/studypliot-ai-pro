from app.database.db import Database
from app.mcp.tools import (
    add_study_task,
    complete_study_task,
    get_study_plan,
    list_open_tasks,
)


def test_mcp_tools_share_task_and_planner_services(tmp_path):
    database = Database(tmp_path / "mcp.sqlite3")
    database.initialize()

    task = add_study_task(
        "Review notes",
        subject="History",
        due_date="2026-10-24",
        estimated_minutes=25,
        database=database,
    )
    open_tasks = list_open_tasks(database)
    assert [item["id"] for item in open_tasks["items"]] == [task["id"]]
    assert open_tasks["total"] == 1
    assert get_study_plan(days=7, database=database)["total_minutes"] == 25
    completed = complete_study_task(task["id"], database)
    assert completed["completed"] is True
    assert list_open_tasks(database)["items"] == []
