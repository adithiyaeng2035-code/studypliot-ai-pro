"""Task creation and management services."""

import calendar
import csv
import io
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from app.database.db import Database


def _task_dict(row: Any) -> dict[str, Any]:
    task = dict(row)
    task.pop("user_id", None)
    task.pop("recurrence_series_id", None)
    task["completed"] = bool(task["completed"])
    return task


def _task_filters(
    status: str, *, search: str = "", subject: str = "", user_id: int | None = None
) -> tuple[str, list[Any]]:
    if status not in {"all", "open", "completed"}:
        raise ValueError("status must be all, open, or completed")
    conditions: list[str] = []
    parameters: list[Any] = []
    if status == "open":
        conditions.append("completed = 0")
    elif status == "completed":
        conditions.append("completed = 1")
    if user_id is not None:
        conditions.append("user_id = ?")
        parameters.append(user_id)
    normalized_search = search.strip()
    if normalized_search:
        conditions.append(
            "(LOWER(title) LIKE LOWER(?) OR LOWER(subject) LIKE LOWER(?) "
            "OR LOWER(description) LIKE LOWER(?))"
        )
        pattern = f"%{normalized_search}%"
        parameters.extend((pattern, pattern, pattern))
    normalized_subject = subject.strip()
    if normalized_subject:
        conditions.append("LOWER(subject) LIKE LOWER(?)")
        parameters.append(f"%{normalized_subject}%")
    return (" WHERE " + " AND ".join(conditions) if conditions else "", parameters)


def count_tasks(
    database: Database, *, status: str = "all", search: str = "", subject: str = "",
    user_id: int | None = None,
) -> int:
    where, parameters = _task_filters(
        status, search=search, subject=subject, user_id=user_id
    )
    with database.session() as connection:
        return connection.execute(
            f"SELECT COUNT(*) AS total FROM tasks{where}", parameters
        ).fetchone()["total"]


def list_tasks(
    database: Database, *, status: str = "all", limit: int = 50, offset: int = 0,
    search: str = "", subject: str = "", user_id: int | None = None,
) -> list[dict[str, Any]]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if offset < 0:
        raise ValueError("offset must not be negative")
    where, parameters = _task_filters(
        status, search=search, subject=subject, user_id=user_id
    )
    query = (
        "SELECT * FROM tasks"
        + where
            + " ORDER BY completed ASC, due_date IS NULL, due_date ASC, id DESC LIMIT ? OFFSET ?"
    )
    parameters.extend((limit, offset))
    with database.session() as connection:
        return [_task_dict(row) for row in connection.execute(query, parameters)]


RECURRENCE_RULES = {"none", "daily", "weekly", "monthly"}


def _normalize_task(
    values: dict[str, Any],
) -> tuple[str, str, str, str | None, int, str, str, str | None, str]:
    title = str(values.get("title", "")).strip()
    if not title:
        raise ValueError("title is required")
    minutes = values.get("estimated_minutes", 30)
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= 1440:
        raise ValueError("estimated_minutes must be between 1 and 1440")
    due_date = values.get("due_date")
    if due_date is not None:
        try:
            due_date = date.fromisoformat(str(due_date)).isoformat()
        except ValueError as error:
            raise ValueError("due_date must be a valid ISO date") from error
    recurrence_rule = str(values.get("recurrence_rule", "none")).lower()
    if recurrence_rule not in RECURRENCE_RULES:
        raise ValueError("recurrence_rule must be none, daily, weekly, or monthly")
    recurrence_until = values.get("recurrence_until")
    if recurrence_until is not None:
        try:
            recurrence_until = date.fromisoformat(str(recurrence_until)).isoformat()
        except ValueError as error:
            raise ValueError("recurrence_until must be a valid ISO date") from error
    if recurrence_rule != "none":
        if due_date is None:
            raise ValueError("a due date is required for a recurring task")
        if recurrence_until is None:
            raise ValueError("repeat through date is required for a recurring task")
        if recurrence_until < due_date:
            raise ValueError("repeat through date cannot be before the first due date")
    elif recurrence_until is not None:
        raise ValueError("repeat through date requires a recurring task")
    created_at = datetime.now(UTC).isoformat()
    subject = str(values.get("subject", "General")).strip() or "General"
    description = str(values.get("description", "")).strip()
    resource_url = str(values.get("resource_url", "")).strip()
    if resource_url:
        parsed_resource = urlsplit(resource_url)
        if parsed_resource.scheme not in {"http", "https"} or not parsed_resource.hostname or parsed_resource.username or parsed_resource.password or len(resource_url) > 2048:
            raise ValueError("resource_url must be a valid HTTP or HTTPS link")
    return (
        title, subject, description, due_date, minutes, created_at,
        recurrence_rule, recurrence_until, resource_url,
    )


def _next_due_date(
    due_date: str, recurrence_rule: str, *, monthly_anchor_day: int | None = None
) -> str:
    current = date.fromisoformat(due_date)
    if recurrence_rule == "daily":
        next_date = current + timedelta(days=1)
    elif recurrence_rule == "weekly":
        next_date = current + timedelta(days=7)
    elif recurrence_rule == "monthly":
        month_index = current.year * 12 + current.month
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        anchor_day = monthly_anchor_day or current.day
        next_date = date(year, month, min(anchor_day, calendar.monthrange(year, month)[1]))
    else:
        raise ValueError("unsupported recurrence rule")
    return next_date.isoformat()


def create_task(
    database: Database, values: dict[str, Any], *, user_id: int | None = None
) -> dict[str, Any]:
    normalized = _normalize_task(values)
    with database.session() as connection:
        insert = """INSERT INTO tasks
                    (title, subject, description, due_date, estimated_minutes, created_at,
                     recurrence_rule, recurrence_until, resource_url, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        parameters = (*normalized, user_id)
        if database.is_postgres:
            task_id = connection.execute(insert + " RETURNING id", parameters).fetchone()["id"]
        else:
            cursor = connection.execute(insert, parameters)
            task_id = cursor.lastrowid
        if normalized[6] != "none":
            connection.execute(
                "UPDATE tasks SET recurrence_series_id = ? WHERE id = ?", (task_id, task_id)
            )
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _task_dict(row)


def create_tasks(
    database: Database, tasks: list[dict[str, Any]], *, user_id: int | None = None
) -> list[dict[str, Any]]:
    """Insert an approved task batch atomically."""
    if not tasks:
        raise ValueError("at least one task is required")
    normalized_tasks = [_normalize_task(task) for task in tasks]
    created = []
    with database.session() as connection:
        insert = """INSERT INTO tasks
                    (title, subject, description, due_date, estimated_minutes, created_at,
                     recurrence_rule, recurrence_until, resource_url, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        for values in normalized_tasks:
            parameters = (*values, user_id)
            if database.is_postgres:
                task_id = connection.execute(insert + " RETURNING id", parameters).fetchone()["id"]
            else:
                task_id = connection.execute(insert, parameters).lastrowid
            if values[6] != "none":
                connection.execute(
                    "UPDATE tasks SET recurrence_series_id = ? WHERE id = ?",
                    (task_id, task_id),
                )
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            created.append(_task_dict(row))
    return created


def import_tasks_csv(
    database: Database, contents: str, *, user_id: int | None = None,
    max_rows: int = 5000,
) -> int:
    """Validate and atomically import a spreadsheet-friendly task CSV."""
    reader = csv.DictReader(io.StringIO(contents))
    if not reader.fieldnames or "title" not in reader.fieldnames:
        raise ValueError("CSV must include a title column")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("CSV contains duplicate column names")
    prepared: list[tuple[tuple[Any, ...], bool, str | None]] = []
    for row_number, row in enumerate(reader, start=2):
        if len(prepared) >= max_rows:
            raise ValueError(f"CSV cannot contain more than {max_rows} tasks")
        if None in row:
            raise ValueError(f"CSV row {row_number} has extra values")
        if row.get("title") is None:
            raise ValueError(f"CSV row {row_number} is missing its title")
        try:
            estimated_minutes = int(row.get("estimated_minutes") or 30)
        except (TypeError, ValueError) as error:
            raise ValueError(f"CSV row {row_number}: estimated_minutes must be an integer") from error
        values = {
            "title": row.get("title", ""),
            "subject": row.get("subject", "General"),
            "description": row.get("description", ""),
            "resource_url": row.get("resource_url", ""),
            "due_date": row.get("due_date") or None,
            "estimated_minutes": estimated_minutes,
            "recurrence_rule": row.get("recurrence_rule") or "none",
            "recurrence_until": row.get("recurrence_until") or None,
        }
        try:
            normalized = _normalize_task(values)
        except (ValueError, TypeError) as error:
            raise ValueError(f"CSV row {row_number}: {error}") from error
        completed_value = (row.get("completed") or "false").strip().lower()
        if completed_value not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError(f"CSV row {row_number}: completed must be true or false")
        source_series = str(row.get("recurrence_series_id") or "").strip() or None
        prepared.append((normalized, completed_value in {"true", "1", "yes"}, source_series))

    if not prepared:
        raise ValueError("CSV does not contain any tasks")
    with database.session() as connection:
        insert = """INSERT INTO tasks
            (title, subject, description, due_date, estimated_minutes, created_at,
             recurrence_rule, recurrence_until, resource_url, completed, completed_at,
             recurrence_series_id, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)"""
        imported_ids: list[tuple[int, tuple[Any, ...], str | None]] = []
        series_ids: dict[str, int] = {}
        for normalized, completed, source_series in prepared:
            completed_at = datetime.now(UTC).isoformat() if completed else None
            values = (*normalized, int(completed), completed_at, user_id)
            if database.is_postgres:
                task_id = connection.execute(insert + " RETURNING id", values).fetchone()["id"]
            else:
                task_id = connection.execute(insert, values).lastrowid
            task_id = int(task_id)
            imported_ids.append((task_id, normalized, source_series))
            if normalized[6] != "none" and source_series and source_series not in series_ids:
                series_ids[source_series] = task_id
        for task_id, normalized, source_series in imported_ids:
            if normalized[6] == "none":
                continue
            series_id = series_ids.get(source_series) if source_series else task_id
            connection.execute(
                "UPDATE tasks SET recurrence_series_id = ? WHERE id = ?",
                (series_id, task_id),
            )
    return len(prepared)


def update_task(
    database: Database, task_id: int, changes: dict[str, Any], *, user_id: int | None = None
) -> dict[str, Any]:
    allowed = {"title", "subject", "description", "resource_url", "due_date", "estimated_minutes", "completed"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"unsupported fields: {', '.join(sorted(unknown))}")
    if not changes:
        raise ValueError("at least one field is required")

    normalized = dict(changes)
    if "title" in normalized:
        if normalized["title"] is None:
            raise ValueError("title cannot be null")
        normalized["title"] = str(normalized["title"]).strip()
        if not normalized["title"]:
            raise ValueError("title cannot be empty")
    if "subject" in normalized:
        if normalized["subject"] is None:
            raise ValueError("subject cannot be null")
        normalized["subject"] = str(normalized["subject"]).strip() or "General"
    if "description" in normalized:
        if normalized["description"] is None:
            raise ValueError("description cannot be null")
        normalized["description"] = str(normalized["description"]).strip()
    if "resource_url" in normalized:
        resource = str(normalized["resource_url"]).strip()
        if resource:
            parsed = urlsplit(resource)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or len(resource) > 2048:
                raise ValueError("resource_url must be a valid HTTP or HTTPS link")
        normalized["resource_url"] = resource
    if "estimated_minutes" in normalized:
        minutes = normalized["estimated_minutes"]
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= 1440:
            raise ValueError("estimated_minutes must be between 1 and 1440")
    if "due_date" in normalized and normalized["due_date"] is not None:
        try:
            normalized["due_date"] = date.fromisoformat(str(normalized["due_date"])).isoformat()
        except ValueError as error:
            raise ValueError("due_date must be a valid ISO date") from error
    if "completed" in normalized:
        if not isinstance(normalized["completed"], bool):
            raise ValueError("completed must be a boolean")
        normalized["completed"] = int(normalized["completed"])
        normalized["completed_at"] = (
            datetime.now(UTC).isoformat() if normalized["completed"] else None
        )

    assignments = ", ".join(f"{field} = ?" for field in normalized)
    values = [*normalized.values(), task_id]
    where = "id = ?"
    if user_id is not None:
        where += " AND user_id = ?"
        values.append(user_id)
    with database.session() as connection:
        existing = connection.execute(
            "SELECT * FROM tasks WHERE " + where, (task_id, user_id) if user_id is not None else (task_id,)
        ).fetchone()
        if existing is None:
            raise KeyError(f"task {task_id} was not found")
        if (
            existing["recurrence_rule"] != "none"
            and "due_date" in normalized
            and normalized["due_date"] != existing["due_date"]
        ):
            raise ValueError("the due date of a recurring occurrence cannot be changed")
        cursor = connection.execute(f"UPDATE tasks SET {assignments} WHERE {where}", values)
        if cursor.rowcount == 0:
            raise KeyError(f"task {task_id} was not found")
        if normalized.get("completed") == 1 and existing["recurrence_rule"] != "none":
            series_id = existing["recurrence_series_id"] or existing["id"]
            series_root = connection.execute(
                "SELECT due_date FROM tasks WHERE id = ?", (series_id,)
            ).fetchone()
            monthly_anchor_day = (
                date.fromisoformat(series_root["due_date"]).day
                if series_root and existing["recurrence_rule"] == "monthly"
                else None
            )
            next_due_date = _next_due_date(
                existing["due_date"], existing["recurrence_rule"],
                monthly_anchor_day=monthly_anchor_day,
            )
            if next_due_date <= existing["recurrence_until"]:
                duplicate = connection.execute(
                    "SELECT id FROM tasks WHERE recurrence_series_id = ? AND due_date = ?",
                    (series_id, next_due_date),
                ).fetchone()
                if duplicate is None:
                    created_at = datetime.now(UTC).isoformat()
                    next_task = (
                        existing["title"], existing["subject"], existing["description"],
                        next_due_date, existing["estimated_minutes"], created_at,
                        existing["recurrence_rule"], existing["recurrence_until"],
                        existing["resource_url"],
                        series_id, existing["user_id"],
                    )
                    connection.execute(
                        """INSERT INTO tasks
                           (title, subject, description, due_date, estimated_minutes, created_at,
                            recurrence_rule, recurrence_until, resource_url, recurrence_series_id, user_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        next_task,
                    )
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _task_dict(row)


def delete_task(database: Database, task_id: int, *, user_id: int | None = None) -> None:
    with database.session() as connection:
        lookup = "SELECT recurrence_rule, recurrence_series_id FROM tasks WHERE id = ?"
        lookup_parameters: tuple[Any, ...] = (task_id,)
        if user_id is not None:
            lookup += " AND user_id = ?"
            lookup_parameters = (task_id, user_id)
        task = connection.execute(lookup, lookup_parameters).fetchone()
        if task is None:
            raise KeyError(f"task {task_id} was not found")
        if task["recurrence_rule"] != "none":
            series_id = task["recurrence_series_id"] or task_id
            delete_series = "DELETE FROM tasks WHERE recurrence_series_id = ?"
            series_parameters: tuple[Any, ...] = (series_id,)
            if user_id is not None:
                delete_series += " AND user_id = ?"
                series_parameters = (series_id, user_id)
            connection.execute(delete_series, series_parameters)
            return
        query = "DELETE FROM tasks WHERE id = ?"
        parameters: tuple[Any, ...] = (task_id,)
        if user_id is not None:
            query += " AND user_id = ?"
            parameters = (task_id, user_id)
        cursor = connection.execute(query, parameters)
        if cursor.rowcount == 0:
            raise KeyError(f"task {task_id} was not found")
