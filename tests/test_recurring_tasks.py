from app.database.db import Database
from app.services.task_service import create_task, delete_task, list_tasks, update_task


def test_monthly_task_creates_next_occurrences_through_end_date(tmp_path):
    database = Database(tmp_path / "recurring.sqlite3")
    database.initialize()
    task = create_task(
        database,
        {
            "title": "Monthly review",
            "due_date": "2026-01-31",
            "recurrence_rule": "monthly",
            "recurrence_until": "2026-03-31",
        },
    )

    update_task(database, task["id"], {"completed": True})
    occurrences = list_tasks(database, limit=10)
    assert [item["due_date"] for item in occurrences] == ["2026-02-28", "2026-01-31"]
    assert occurrences[0]["recurrence_rule"] == "monthly"

    next_task = occurrences[0]
    update_task(database, next_task["id"], {"completed": True})
    third_task = next(item for item in list_tasks(database, limit=10) if item["due_date"] == "2026-03-31")
    update_task(database, third_task["id"], {"completed": True})
    update_task(database, third_task["id"], {"completed": True})

    final_tasks = list_tasks(database, limit=10)
    assert sorted(item["due_date"] for item in final_tasks) == [
        "2026-01-31", "2026-02-28", "2026-03-31"
    ]
    assert sum(item["completed"] for item in final_tasks) == 3


def test_recurring_task_requires_dates_and_valid_rule(tmp_path):
    database = Database(tmp_path / "recurring-validation.sqlite3")
    database.initialize()

    for values, message in (
        ({"title": "Daily review", "recurrence_rule": "daily"}, "due date is required"),
        ({"title": "Daily review", "due_date": "2026-10-20", "recurrence_rule": "daily"}, "repeat through date is required"),
        ({"title": "Review", "recurrence_rule": "sometimes"}, "recurrence_rule"),
    ):
        try:
            create_task(database, values)
        except ValueError as error:
            assert message in str(error)
        else:
            raise AssertionError(f"expected validation error containing {message!r}")


def test_deleting_a_recurring_occurrence_removes_its_series(tmp_path):
    database = Database(tmp_path / "recurring-delete.sqlite3")
    database.initialize()
    root = create_task(
        database,
        {
            "title": "Weekly review",
            "due_date": "2026-10-20",
            "recurrence_rule": "weekly",
            "recurrence_until": "2026-11-03",
        },
    )
    update_task(database, root["id"], {"completed": True})
    generated = next(item for item in list_tasks(database, limit=10) if not item["completed"])

    delete_task(database, generated["id"])

    assert list_tasks(database, limit=10) == []
