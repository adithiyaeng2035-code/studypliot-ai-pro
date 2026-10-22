# Architecture

StudyPilot is a single-process FastAPI application with a static browser frontend
and SQLite or PostgreSQL storage.

- `app/api/routes.py` serves JSON endpoints and the files in `frontend/`.
- `app/services/` contains task CRUD, due-date summaries, rule-based planning,
  persisted focus-session history, and progress aggregation plus bounded evidence
  summaries for model-assisted review.
- `app/database/` owns database connection lifecycles and ordered, backend-specific
  SQL migrations. Applied versions are recorded in `schema_migrations`.
- `app/ai/` provides local next-step suggestions, structured cross-subject doubt
  explanations, and validated study-plan drafts through an optional
  OpenAI-compatible chat completion client.
- `app/mcp/` exposes task and planning operations as MCP tools over stdio.

The default database is `data/studypilot.sqlite3`; `STUDYPILOT_DATABASE` can
override the SQLite path. Setting `DATABASE_URL` selects PostgreSQL instead.
The default configuration is local and single-user. Setting `AUTH_ENABLED=true`
enables hosted accounts with hashed passwords, expiring server-side sessions,
CSRF-protected mutations, and per-user ownership on tasks and study sessions.
The first account requires `AUTH_BOOTSTRAP_TOKEN` and adopts legacy unowned data;
later accounts receive separate data. MCP tools are disabled in authenticated
mode because the stdio server has no browser account context.
Database initialization applies unapplied files from `app/database/migrations/`
in version order. Existing task and study-session tables are retained because the
initial migrations use `CREATE TABLE IF NOT EXISTS`; applied versions are recorded
in the `schema_migrations` table. Add future schema changes as a new numbered SQL
file for each supported backend rather than editing a migration that has shipped.
The dashboard can export a complete JSON backup and restore it additively through
`POST /api/imports/backup`. Restore validates the backup format and record fields,
maps study sessions to their restored tasks, and leaves existing records intact.
Importing the same file more than once creates duplicate records.
Task-list API requests are paginated and bounded to 100 rows per request. Indexes
support task status and due-date ordering. The dashboard shows bounded deadline
and per-day plan samples with complete counts and study-time totals.
The dashboard can request `POST /api/progress/analyze`, which sends aggregated
task and subject progress counts to the configured chat model. It does not train
a model on personal history or send task descriptions.
Completed focus sessions are stored separately in `study_sessions`; linking a
session to a task is optional, and deleting a task keeps the session history.
The Doubt Solver page calls `POST /api/doubts/solve`; AI provider configuration is
required, and submitted question content is sent to that provider.
The shared AI client validates HTTP(S) provider base URLs, caps prompt and response
sizes and output tokens, applies a 30-second timeout, and avoids returning raw
provider error bodies to the browser.
HTTP requests emit one-line JSON logs with method, path, status, and duration,
without request bodies. `GET /api/health` checks database connectivity and reports
AI provider configuration as informational because AI is optional; database
failure returns HTTP 503 without exposing connection details.
GitHub Actions runs lint, compilation, tests, an OpenAPI route-contract check,
and a dependency audit on Python 3.10 and 3.13.
The AI Study Planner returns validated, reviewable drafts. `POST /api/plans/approve`
validates the confirmed schedule again and atomically adds its sessions as tasks.
