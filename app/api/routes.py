"""HTTP API and static frontend."""

import csv
import hmac
import io
import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.ai.assistant import answer_question, tutor_chat
from app.ai.doubt_solver import solve_doubt
from app.ai.llm_client import AIProviderNotConfigured, is_configured
from app.ai.progress_analysis import analyze_progress
from app.ai.study_planning import execute_approved_plan, generate_study_plan
from app.config import (
    AUTH_COOKIE_SECURE,
    AUTH_ENABLED,
    DATABASE_BACKEND,
    DATABASE_PATH,
    DATABASE_URL,
    PROJECT_ROOT,
)
from app.database.db import Database
from app.logging_config import configure_logging
from app.services.auth_service import (
    LoginRateLimited,
    authenticate_user,
    create_session,
    delete_account,
    register_user,
    resolve_session,
    revoke_session,
)
from app.services.backup_service import restore_backup
from app.services.calendar_service import get_calendar_events
from app.services.deadline_service import get_deadlines
from app.services.document_extractor import (
    MAX_DOCUMENT_BYTES,
    DocumentExtractionError,
    extract_document,
)
from app.services.progress_service import get_progress
from app.services.progress_trends import get_progress_trends
from app.services.study_planner import create_study_plan
from app.services.study_session_service import (
    create_study_session,
    get_focus_time_analysis,
    list_study_sessions,
)
from app.services.task_service import (
    count_tasks,
    create_task,
    delete_task,
    import_tasks_csv,
    list_tasks,
    update_task,
)


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    subject: str = Field(default="General", max_length=100)
    description: str = Field(default="", max_length=2000)
    due_date: date | None = None
    estimated_minutes: int = Field(default=30, ge=1, le=1440)
    recurrence_rule: Literal["none", "daily", "weekly", "monthly"] = "none"
    recurrence_until: date | None = None
    resource_url: str = Field(default="", max_length=2048)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    resource_url: str | None = Field(default=None, max_length=2048)
    due_date: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    completed: bool | None = None


class AssistantQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)


class TutorTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class TutorChatQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    history: list[TutorTurn] = Field(default_factory=list, max_length=8)
    study_context: str = Field(default="", max_length=500)
    mode: Literal[
        "general", "learn", "exam_prep", "industry", "writing", "coding",
        "planning", "brainstorm", "time_coach",
    ] = "general"


class DoubtQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=5000)
    level: str = Field(default="", max_length=100)
    context: str = Field(default="", max_length=2000)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=300)
    subject: str = Field(min_length=1, max_length=100)
    deadline: date
    level: str = Field(default="", max_length=100)
    study_days_per_week: int = Field(default=5, ge=1, le=7)
    minutes_per_day: int = Field(default=45, ge=15, le=240)


class PlanSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    estimated_minutes: int = Field(ge=1, le=240)


class PlanApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=300)
    subject: str = Field(min_length=1, max_length=100)
    start_date: date
    deadline: date
    study_days_per_week: int = Field(ge=1, le=7)
    minutes_per_day: int = Field(ge=15, le=240)
    sessions: list[PlanSession] = Field(min_length=1, max_length=90)
    total_minutes: int | None = Field(default=None, ge=0)


class BackupTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    subject: str = Field(max_length=100)
    description: str = Field(max_length=2000)
    due_date: date | None = None
    estimated_minutes: int = Field(ge=1, le=1440)
    completed: bool
    created_at: str = Field(min_length=1, max_length=64)
    completed_at: str | None = Field(default=None, max_length=64)
    recurrence_rule: Literal["none", "daily", "weekly", "monthly"] = "none"
    recurrence_until: date | None = None
    recurrence_series_id: int | None = Field(default=None, gt=0)
    resource_url: str = Field(default="", max_length=2048)


class BackupStudySession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    task_id: int | None = Field(default=None, gt=0)
    task_title: str | None = Field(default=None, max_length=200)
    subject: str = Field(max_length=100)
    duration_minutes: int = Field(ge=1, le=240)
    notes: str = Field(max_length=2000)
    started_at: str = Field(min_length=1, max_length=64)
    completed_at: str = Field(min_length=1, max_length=64)
    created_at: str = Field(min_length=1, max_length=64)


class BackupRestore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: Literal["StudyPilot"]
    schema_version: Literal[1]
    exported_at: str = Field(min_length=1, max_length=64)
    tasks: list[BackupTask] = Field(max_length=50000)
    study_sessions: list[BackupStudySession] = Field(max_length=100000)


class AuthRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class AuthLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AuthDeleteAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128)


class StudySessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int | None = Field(default=None, ge=1)
    subject: str = Field(default="General", max_length=100)
    duration_minutes: int = Field(ge=1, le=240)
    notes: str = Field(default="", max_length=1000)
    started_at: datetime
    completed_at: datetime


def create_app(
    database: Database | None = None, frontend_dir: str | Path | None = None
) -> FastAPI:
    logger = configure_logging()
    application = FastAPI(title="StudyPilot", version="1.0.0")
    target = DATABASE_URL or (
        "postgresql" if DATABASE_BACKEND == "postgresql" else DATABASE_PATH
    )
    app_database = database or Database(target)
    app_database.initialize()
    application.state.database = app_database
    application.state.auth_enabled = AUTH_ENABLED
    cookie_name = "__Host-StudyPilotSession" if AUTH_COOKIE_SECURE else "studypilot_session"
    public_auth_paths = {
        "/api/auth/me",
        "/api/auth/register",
        "/api/auth/login",
    }
    public_static_paths = {
        "/login.html", "/auth.js", "/auth-client.js", "/auth.css",
        "/style.css", "/doubts.css", "/planner.css",
    }

    @application.middleware("http")
    async def log_http_requests(request, call_next):
        started_at = time.perf_counter()
        request.state.auth_user = None
        request.state.csrf_token = None
        if AUTH_ENABLED:
            auth_user = resolve_session(
                app_database, request.cookies.get(cookie_name)
            )
            request.state.auth_user = auth_user
            path = request.url.path
            if path.startswith("/api/") and path not in public_auth_paths and path != "/api/health" and path != "/api/ai/status":
                if auth_user is None:
                    return JSONResponse({"detail": "authentication required"}, status_code=401)
                request.state.csrf_token = auth_user["csrf_token"]
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    supplied_token = request.headers.get("x-csrf-token", "")
                    if not hmac.compare_digest(supplied_token, auth_user["csrf_token"]):
                        return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)
            elif not path.startswith("/api/") and path not in public_static_paths:
                if auth_user is None:
                    return RedirectResponse("/login.html", status_code=303)
        try:
            response = await call_next(request)
        except Exception as error:
            logger.error(
                "http_request_failed",
                extra={
                    "event": "http_request_failed",
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(error).__name__,
                },
            )
            raise
        logger.info(
            "http_request_complete",
            extra={
                "event": "http_request_complete",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        return response

    def request_user_id(request: Request) -> int | None:
        user = getattr(request.state, "auth_user", None)
        return int(user["id"]) if AUTH_ENABLED and user else None

    @application.post("/api/auth/register", status_code=201)
    def register(payload: AuthRegister) -> Response:
        if not AUTH_ENABLED:
            raise HTTPException(status_code=404, detail="account authentication is disabled")
        try:
            user = register_user(
                app_database,
                email=payload.email,
                password=payload.password,
                full_name=payload.full_name,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        token, csrf_token = create_session(app_database, user["id"])
        response = JSONResponse({"user": user, "csrf_token": csrf_token}, status_code=201)
        response.set_cookie(
            cookie_name, token, max_age=12 * 60 * 60, httponly=True,
            secure=AUTH_COOKIE_SECURE, samesite="lax", path="/",
        )
        return response

    @application.post("/api/auth/login")
    def login(payload: AuthLogin, request: Request) -> Response:
        if not AUTH_ENABLED:
            raise HTTPException(status_code=404, detail="account authentication is disabled")
        source_address = request.client.host if request.client else "unknown"
        try:
            user = authenticate_user(
                app_database, email=payload.email, password=payload.password,
                source_address=source_address,
            )
        except LoginRateLimited as error:
            raise HTTPException(
                status_code=429,
                detail=str(error),
                headers={"Retry-After": "900"},
            ) from error
        if user is None:
            raise HTTPException(status_code=401, detail="email or password is incorrect")
        token, csrf_token = create_session(app_database, user["id"])
        response = JSONResponse({"user": user, "csrf_token": csrf_token})
        response.set_cookie(
            cookie_name, token, max_age=12 * 60 * 60, httponly=True,
            secure=AUTH_COOKIE_SECURE, samesite="lax", path="/",
        )
        return response

    @application.get("/api/auth/me")
    def auth_me(request: Request) -> dict[str, Any]:
        if not AUTH_ENABLED:
            return {"auth_enabled": False, "authenticated": False}
        user = request.state.auth_user
        if user is None:
            return {"auth_enabled": True, "authenticated": False}
        return {
            "auth_enabled": True,
            "authenticated": True,
            "user": {"id": user["id"], "email": user["email"], "full_name": user["full_name"]},
            "csrf_token": user["csrf_token"],
        }

    @application.post("/api/auth/logout")
    def logout(request: Request) -> Response:
        revoke_session(app_database, request.cookies.get(cookie_name))
        response = JSONResponse({"status": "signed_out"})
        response.delete_cookie(cookie_name, httponly=True, secure=AUTH_COOKIE_SECURE, samesite="lax", path="/")
        return response

    @application.delete("/api/auth/account")
    def delete_own_account(payload: AuthDeleteAccount, request: Request) -> Response:
        user_id = request_user_id(request)
        if user_id is None:
            raise HTTPException(status_code=401, detail="authentication required")
        if not delete_account(app_database, user_id, payload.password):
            raise HTTPException(status_code=403, detail="password is incorrect")
        response = Response(status_code=204)
        response.delete_cookie(cookie_name, httponly=True, secure=AUTH_COOKIE_SECURE, samesite="lax", path="/")
        return response

    @application.get("/api/health")
    def health() -> Response:
        try:
            with app_database.session() as connection:
                connection.execute("SELECT 1")
        except Exception as error:  # noqa: BLE001 - any database health-check error means unavailable
            logger.warning(
                "database_health_check_failed",
                extra={"event": "database_health_check_failed", "error_type": type(error).__name__},
            )
            return Response(
                content=json.dumps({
                    "status": "error",
                    "database": "unavailable",
                    "ai_provider": "configured" if is_configured() else "not_configured",
                }),
                status_code=503,
                media_type="application/json",
            )
        return Response(
            content=json.dumps({
                "status": "ok",
                "database": "ok",
                "ai_provider": "configured" if is_configured() else "not_configured",
            }),
            media_type="application/json",
        )

    @application.get("/api/ai/status")
    def ai_status() -> dict[str, bool]:
        return {"configured": is_configured()}

    @application.post("/api/doubts/solve")
    def solve_student_doubt(payload: DoubtQuestion) -> dict:
        try:
            return solve_doubt(
                subject=payload.subject,
                question=payload.question,
                level=payload.level,
                context=payload.context,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except AIProviderNotConfigured as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @application.post("/api/doubts/analyze-document")
    async def analyze_doubt_document(
        document: UploadFile = File(...),
        subject: str = Form(default="Document analysis", max_length=100),
        question: str = Form(default="", max_length=5000),
        level: str = Form(default="", max_length=100),
    ) -> dict:
        if not is_configured():
            raise HTTPException(
                status_code=503,
                detail="AI is not configured. Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL on the server.",
            )
        try:
            contents = await document.read(MAX_DOCUMENT_BYTES + 1)
        finally:
            await document.close()
        try:
            extracted = extract_document(document.filename or "", contents)
        except DocumentExtractionError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        prompt = question.strip() or (
            "Analyze this file. Give a brief summary and then an understandable, detailed "
            "solution or interpretation based on the supplied pages or spreadsheet cells. "
            "For numeric work, show the formula, substitutions, units, and result where applicable."
        )
        try:
            result = solve_doubt(
                subject=subject.strip() or "Document analysis",
                question=prompt,
                level=level,
                document_text=str(extracted["text"]),
            )
            filename = (document.filename or "uploaded document").replace("\\", "/").rsplit("/", 1)[-1]
            result["document"] = {
                "filename": filename,
                "kind": extracted["kind"],
                "sources": extracted["sources"],
                "truncated": extracted["truncated"],
            }
            return result
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except AIProviderNotConfigured as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @application.post("/api/plans/generate")
    def generate_plan(payload: PlanRequest, request: Request) -> dict:
        try:
            user_id = request_user_id(request)
            owner = " AND user_id = ?" if user_id is not None else ""
            params: tuple[Any, ...] = (date.today().isoformat(), payload.deadline.isoformat())
            if user_id is not None:
                params += (user_id,)
            with app_database.session() as connection:
                workload_rows = connection.execute(
                    """SELECT due_date AS date, COUNT(*) AS open_tasks,
                              COALESCE(SUM(estimated_minutes), 0) AS estimated_minutes
                       FROM tasks WHERE completed = 0
                         AND (due_date IS NULL OR due_date BETWEEN ? AND ?)""" + owner
                    + " GROUP BY due_date ORDER BY due_date LIMIT 92",
                    params,
                ).fetchall()
            return generate_study_plan(
                goal=payload.goal,
                subject=payload.subject,
                deadline=payload.deadline,
                level=payload.level,
                study_days_per_week=payload.study_days_per_week,
                minutes_per_day=payload.minutes_per_day,
                existing_workload=[dict(row) for row in workload_rows],
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except AIProviderNotConfigured as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @application.post("/api/plans/approve", status_code=201)
    def approve_plan(payload: PlanApproval, request: Request) -> dict:
        plan = payload.model_dump(exclude={"total_minutes"})
        plan["start_date"] = payload.start_date.isoformat()
        plan["deadline"] = payload.deadline.isoformat()
        for session in plan["sessions"]:
            session["date"] = session["date"].isoformat()
        try:
            tasks = execute_approved_plan(
                app_database, plan, user_id=request_user_id(request)
            )
            return {"created_count": len(tasks), "tasks": tasks}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @application.get("/api/tasks")
    def get_tasks(
        request: Request,
        status: Literal["all", "open", "completed"] = "all",
        search: str = Query(default="", max_length=100),
        subject: str = Query(default="", max_length=100),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=100),
    ) -> dict:
        user_id = request_user_id(request)
        total = count_tasks(
            app_database, status=status, search=search, subject=subject, user_id=user_id
        )
        pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, pages)
        return {
            "items": list_tasks(
                app_database, status=status, limit=page_size,
                offset=(page - 1) * page_size, search=search, subject=subject,
                user_id=user_id,
            ),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    @application.post("/api/tasks", status_code=201)
    def post_task(payload: TaskCreate, request: Request) -> dict:
        values = payload.model_dump()
        values["due_date"] = payload.due_date.isoformat() if payload.due_date else None
        values["recurrence_until"] = (
            payload.recurrence_until.isoformat() if payload.recurrence_until else None
        )
        try:
            return create_task(app_database, values, user_id=request_user_id(request))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @application.patch("/api/tasks/{task_id}")
    def patch_task(task_id: int, payload: TaskUpdate, request: Request) -> dict:
        changes = payload.model_dump(exclude_unset=True)
        if isinstance(changes.get("due_date"), date):
            changes["due_date"] = changes["due_date"].isoformat()
        try:
            return update_task(
                app_database, task_id, changes, user_id=request_user_id(request)
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @application.delete("/api/tasks/{task_id}", status_code=204)
    def remove_task(task_id: int, request: Request) -> Response:
        try:
            delete_task(app_database, task_id, user_id=request_user_id(request))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return Response(status_code=204)

    @application.get("/api/progress")
    def progress(request: Request) -> dict:
        return get_progress(app_database, user_id=request_user_id(request))

    @application.get("/api/progress/trends")
    def progress_trends(
        request: Request, days: int = Query(default=30, ge=7, le=90)
    ) -> dict:
        try:
            return get_progress_trends(
                app_database, days=days, user_id=request_user_id(request)
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @application.get("/api/study-sessions")
    def study_sessions(
        request: Request, limit: int = Query(default=20, ge=1, le=100)
    ) -> dict:
        return list_study_sessions(
            app_database, limit=limit, user_id=request_user_id(request)
        )

    @application.get("/api/calendar")
    def calendar_events(
        request: Request,
        start: date = Query(default_factory=date.today),
        days: int = Query(default=7, ge=1, le=42),
    ) -> dict:
        return get_calendar_events(
            app_database, start=start, days=days, user_id=request_user_id(request)
        )

    @application.get("/api/exports/calendar.ics")
    def export_calendar_ics(
        request: Request,
        start: date = Query(default_factory=date.today),
        days: int = Query(default=90, ge=1, le=365),
    ) -> Response:
        """Export due dates and focus sessions as an iCalendar file."""
        end = start + timedelta(days=days)
        user_id = request_user_id(request)
        owner = " AND user_id = ?" if user_id is not None else ""
        params: tuple[Any, ...] = (start.isoformat(), end.isoformat())
        if user_id is not None:
            params += (user_id,)
        with app_database.session() as connection:
            tasks = connection.execute(
                """SELECT id, title, subject, due_date, estimated_minutes, completed
                   FROM tasks WHERE due_date >= ? AND due_date < ?""" + owner + " ORDER BY due_date, id",
                params,
            ).fetchall()
            sessions = connection.execute(
                """SELECT id, subject, duration_minutes, started_at, completed_at
                   FROM study_sessions WHERE started_at >= ? AND started_at < ?""" + owner + " ORDER BY started_at",
                params,
            ).fetchall()

        def escape_ical(value: str) -> str:
            value = value.replace("\r\n", "\n").replace("\r", "\n")
            value = "".join(character for character in value if character == "\n" or ord(character) >= 32)
            return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

        def fold_ical_line(value: str) -> str:
            chunks: list[str] = []
            current = ""
            for character in value:
                limit = 75 if not chunks else 74
                if current and len((current + character).encode("utf-8")) > limit:
                    chunks.append(current)
                    current = character
                else:
                    current += character
            chunks.append(current)
            return "\r\n ".join(chunks)

        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//StudyPilot//Study Calendar//EN", "CALSCALE:GREGORIAN"]
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        for task in tasks:
            due = date.fromisoformat(task["due_date"])
            lines.extend([
                "BEGIN:VEVENT", f"UID:studypilot-task-{task['id']}@studypilot",
                f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
                f"SUMMARY:{escape_ical(task['title'])}",
                f"DESCRIPTION:{escape_ical(str(task['subject']))} - {int(task['estimated_minutes'])} minutes" + (" - Completed" if task["completed"] else ""),
                "END:VEVENT",
            ])
        for session in sessions:
            try:
                started = datetime.fromisoformat(session["started_at"])
                finished = datetime.fromisoformat(session["completed_at"])
            except ValueError:
                continue
            lines.extend([
                "BEGIN:VEVENT", f"UID:studypilot-session-{session['id']}@studypilot",
                f"DTSTAMP:{stamp}", f"DTSTART:{started.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}",
                f"DTEND:{finished.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{escape_ical(str(session['subject']) + ' study session')}",
                f"DESCRIPTION:{int(session['duration_minutes'])} focus minutes", "END:VEVENT",
            ])
        lines.append("END:VCALENDAR")
        return Response(
            content="\r\n".join(fold_ical_line(line) for line in lines) + "\r\n", media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="studypilot-calendar.ics"'},
        )

    @application.get("/api/exports/tasks.csv")
    def export_tasks_csv(request: Request) -> Response:
        """Download all tasks as a spreadsheet-friendly CSV."""
        columns = (
            "id", "title", "subject", "description", "resource_url", "due_date",
            "estimated_minutes", "completed", "created_at", "completed_at",
            "recurrence_rule", "recurrence_until", "recurrence_series_id",
        )
        user_id = request_user_id(request)
        owner_filter = " WHERE user_id = ?" if user_id is not None else ""
        owner_parameters = (user_id,) if user_id is not None else ()
        with app_database.session() as connection:
            rows = connection.execute(
                "SELECT " + ", ".join(columns) +
                " FROM tasks" + owner_filter + " ORDER BY id",
                owner_parameters,
            ).fetchall()

        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            values = [row[column] for column in columns]
            values[7] = bool(values[7])
            # Prefix formula-like text so opening the CSV in a spreadsheet cannot
            # execute user-entered task content as a formula.
            values = [
                "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
                for value in values
            ]
            writer.writerow(values)
        filename = f"studypilot-tasks-{date.today().isoformat()}.csv"
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @application.get("/api/exports/backup.json")
    def export_backup_json(request: Request) -> Response:
        """Download a complete JSON backup of tasks and focus-session history."""
        user_id = request_user_id(request)
        owner_filter = " WHERE user_id = ?" if user_id is not None else ""
        session_owner_filter = " WHERE study_sessions.user_id = ?" if user_id is not None else ""
        owner_parameters = (user_id,) if user_id is not None else ()
        with app_database.session() as connection:
            tasks = connection.execute(
                """SELECT id, title, subject, description, resource_url, due_date,
                          estimated_minutes, completed, created_at, completed_at,
                          recurrence_rule, recurrence_until, recurrence_series_id
                   FROM tasks""" + owner_filter + " ORDER BY id",
                owner_parameters,
            ).fetchall()
            sessions = connection.execute(
                """SELECT study_sessions.id, study_sessions.task_id, study_sessions.subject,
                          study_sessions.duration_minutes, study_sessions.notes,
                          study_sessions.started_at, study_sessions.completed_at,
                          study_sessions.created_at, tasks.title AS task_title
                   FROM study_sessions
                   LEFT JOIN tasks ON tasks.id = study_sessions.task_id
                   """ + session_owner_filter + " ORDER BY study_sessions.id",
                owner_parameters,
            ).fetchall()
        backup = {
            "app": "StudyPilot",
            "schema_version": 1,
            "exported_at": datetime.now(UTC).isoformat(),
            "tasks": [dict(row) for row in tasks],
            "study_sessions": [dict(row) for row in sessions],
        }
        filename = f"studypilot-backup-{date.today().isoformat()}.json"
        return Response(
            content=json.dumps(backup, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @application.post("/api/imports/backup")
    def import_backup(payload: BackupRestore, request: Request) -> dict[str, int | str]:
        """Restore a StudyPilot backup additively, preserving current records."""
        try:
            result = restore_backup(
                app_database, payload.model_dump(), user_id=request_user_id(request)
            )
            return {"status": "restored", **result}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @application.post("/api/imports/tasks.csv")
    async def import_tasks_csv_file(
        request: Request, file: UploadFile = File(...)
    ) -> dict[str, int | str]:
        """Import validated task rows from a UTF-8 CSV file."""
        max_bytes = 5 * 1024 * 1024
        try:
            contents = await file.read(max_bytes + 1)
        finally:
            await file.close()
        if len(contents) > max_bytes:
            raise HTTPException(status_code=413, detail="CSV file must be 5 MB or smaller")
        try:
            text = contents.decode("utf-8-sig")
            count = import_tasks_csv(
                app_database, text, user_id=request_user_id(request)
            )
            return {"status": "imported", "tasks_added": count}
        except UnicodeDecodeError as error:
            raise HTTPException(status_code=400, detail="CSV file must use UTF-8 encoding") from error
        except csv.Error as error:
            raise HTTPException(status_code=400, detail="CSV file is malformed") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @application.post("/api/study-sessions", status_code=201)
    def post_study_session(payload: StudySessionCreate, request: Request) -> dict:
        try:
            return create_study_session(
                app_database, payload.model_dump(), user_id=request_user_id(request)
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @application.post("/api/progress/analyze")
    def analyze_study_progress(request: Request) -> dict:
        try:
            user_id = request_user_id(request)
            if user_id is None:
                return analyze_progress(app_database)
            return analyze_progress(app_database, user_id=user_id)
        except AIProviderNotConfigured as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @application.get("/api/deadlines")
    def deadlines(
        request: Request,
        days: int = Query(default=7, ge=1, le=90),
        limit: int = Query(default=10, ge=1, le=25),
    ) -> dict:
        return get_deadlines(
            app_database, days=days, limit=limit, user_id=request_user_id(request)
        )

    @application.get("/api/plan")
    def study_plan(request: Request, days: int = Query(default=7, ge=1, le=30)) -> dict:
        return create_study_plan(
            app_database, days=days, user_id=request_user_id(request)
        )

    @application.post("/api/assistant")
    def assistant(payload: AssistantQuestion, request: Request) -> dict:
        try:
            return answer_question(
                app_database, payload.message, user_id=request_user_id(request)
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @application.post("/api/tutor/chat")
    def chat_with_tutor(payload: TutorChatQuestion, request: Request) -> dict:
        try:
            history = [turn.model_dump() for turn in payload.history]
            focus_summary = (
                get_focus_time_analysis(
                    app_database, user_id=request_user_id(request)
                )
                if payload.mode == "time_coach" and is_configured()
                else None
            )
            return tutor_chat(
                payload.message,
                history,
                payload.mode,
                payload.study_context,
                focus_summary,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    static_directory = Path(frontend_dir or PROJECT_ROOT / "frontend")
    application.mount("/", StaticFiles(directory=static_directory, html=True), name="frontend")
    return application


app = create_app()
