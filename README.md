# StudyPilot AI Pro

StudyPilot is a local-first study planner for managing assignments, deadlines, and
study progress. The core app works without an AI provider; connecting an
OpenAI-compatible chat completion endpoint enables conversational study support.

## Requirements

- Python 3.10+
- An internet connection only when installing dependencies or using a configured AI provider

## Run locally

From the project root, create and activate a virtual environment, then install
dependencies and start the app:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.main
```

Open <http://127.0.0.1:8000>. Tasks and progress are stored in
`data/studypilot.sqlite3` by default. Set `STUDYPILOT_DATABASE` to use another
SQLite database path.

To use student registration and login locally, start with `.\run-local-auth.ps1`.
It enables account-scoped SQLite data. Registration saves the student's name,
email, and password hash; the signed-in StudyPilot pages display the student's
name. Existing accounts without a name display their email instead.

The AI study tutor at `/tutor.html` supports follow-up chat with the configured
OpenAI-compatible provider. Microphone dictation and read-aloud use the browser's
built-in speech APIs and may require microphone permission and a supported browser.

## Deploy publicly on Vercel

For a public deployment, use managed PostgreSQL and enable hosted authentication
so visitor data is separated by account. Follow [the Vercel deployment guide](docs/deploy_vercel.md)
before creating a production deployment. The Vercel entrypoint and Python
version are configured in `pyproject.toml` and `.python-version`.

## Connect PostgreSQL

PostgreSQL uses port `5432` by default. Create a database and login in PostgreSQL,
then set the libpq environment variables in PowerShell before starting StudyPilot.
For a database named `alexa` and user `adi_123`:

```powershell
$env:DATABASE_BACKEND = "postgresql"
$env:PGHOST = "localhost"
$env:PGPORT = "5432"
$env:PGDATABASE = "alexa"
$env:PGUSER = "adi_123"
$securePassword = Read-Host "Password for adi_123" -AsSecureString
$env:PGPASSWORD = (New-Object System.Net.NetworkCredential("", $securePassword)).Password
python -m app.main
```

`Read-Host -AsSecureString` prompts locally. Never put the password in this
README, a committed `.env` file, or a chat. Alternatively, set `DATABASE_URL`
privately if you already have a connection URL. On startup, StudyPilot applies
unapplied versioned migrations. When
`DATABASE_BACKEND` and `DATABASE_URL` are unset, the app uses SQLite.

The MCP server also uses the selected database. Keep the `PG*` settings in the
same shell where you run the web app or MCP server.
On startup, the app applies any unapplied versioned SQL migrations from
`app/database/migrations/`. Existing task and study-session data is preserved.

### Enable hosted accounts

Account access is off for the default local single-user setup. For a hosted
deployment, enable authentication behind HTTPS:

```powershell
$env:AUTH_ENABLED = "true"
$env:AUTH_ALLOW_REGISTRATION = "true"
python -m app.main
```

The first account adopts any existing unowned tasks and focus sessions. New accounts receive
separate data. Registration is open by default after the first account; set
`AUTH_ALLOW_REGISTRATION=false` to close it. `AUTH_COOKIE_SECURE` defaults to
`true` when authentication is enabled, so serve the app through HTTPS. For local
HTTP-only authentication testing, explicitly set `AUTH_COOKIE_SECURE=false`.
Login sessions expire after 12 hours, use HttpOnly cookies and CSRF tokens, and
are invalidated when the user signs out. Passwords are stored with Argon2 hashes;
sign-in attempts are throttled. The MCP stdio server is disabled in authenticated
mode because its local tools do not have a browser account identity.

Hosted users can export their own tasks and focus-session history as JSON. The
account menu explains which information AI features send to the configured
provider. A signed-in user can permanently delete their account and study data
from any main page after confirming their password. The account deletion cannot
be undone; export a backup first if you want to keep a copy.

## Features

- Create, complete, filter, and delete study tasks.
- Schedule daily, weekly, or monthly recurring tasks through an end date. Completing
  an occurrence creates the next one; deleting a recurring task removes its series.
- Browse large task collections with server-side pagination (50 per page, up to
  100 per API request); planner and deadline panels return bounded task samples
  while retaining accurate totals.
- Search task titles, subjects, and descriptions, then narrow the paginated list
  by subject or task status.
- Assign a subject, due date, description, and estimated study duration.
- Run a pauseable focus timer, optionally link it to an open task, and review
  persisted study-session history. Actual focus minutes appear in the dashboard
  and are included in the progress-review evidence.
- Set a daily focus-time goal and track today's saved study minutes against a
  seven-day activity chart. The goal preference is saved per account in the browser.
- View upcoming/overdue deadlines, a due-date-based seven-day plan, and progress.
- View due tasks and completed focus sessions in a week or month calendar.
- Ask for a local next-step suggestion without sending data anywhere.
- Optionally configure an OpenAI-compatible chat completion service using
  `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.
- Use the Doubt Solver across subjects and study levels, including school, B.Tech,
  and M.Tech, for an AI-generated explanation, reasoning steps, concept summary,
  likely misconception, and check-for-understanding question.
- Use the AI tutor for multilingual subject explanations, exam preparation by
  class / degree / board / university, industry applications, and study-time
  coaching from saved focus sessions over the last 7 and 30 days.
- Request an on-demand, model-assisted progress review with strengths, focus
  areas, evidence-based actions, and a link into the approval-based study planner.
- Generate a goal-based AI study-plan draft, review it, and explicitly approve
  sessions before they are created as dated tasks.
- Download tasks as spreadsheet-friendly CSV, export a JSON backup containing
  all tasks and focus-session history, and restore a validated backup additively.
- Optionally enable hosted accounts with separate task, plan, progress, and
  focus-session data for each student.
- Review the AI sharing notice, export account data, or delete an account and its
  data from the account menu when hosted authentication is enabled.
- Run the MCP tool server with `python -m app.mcp.server` after installing
  requirements.

### Enable the OpenAI chatbot and AI features

For local development on Windows, run `.\run-openai.ps1` from PowerShell.
It asks for your API key without displaying it, sets the OpenAI endpoint and
model for the app process, and starts StudyPilot. Stop an already-running app
first. The key is removed from the process environment when the app exits.

Alternatively, set the environment variables manually in a PowerShell window:

```powershell
$env:LLM_BASE_URL = "https://api.openai.com/v1"
$env:LLM_MODEL = "gpt-4o-mini"
$secureApiKey = Read-Host "OpenAI API key" -AsSecureString
$env:LLM_API_KEY = (New-Object System.Net.NetworkCredential("", $secureApiKey)).Password
python -m app.main
```

Keep that window open while using StudyPilot. If the app is already running,
stop it first, then launch it from this same configured window. The Doubt Solver
page's provider status should show it as configured after restart. The API key
is held only in that process environment; never commit it, put it in a URL, or
paste it into chat. Create/manage the key in your OpenAI account and ensure API
access and billing are enabled.

The chatbot sends the current question and up to eight recent chat messages to
the configured provider. Progress insights send
aggregate task and subject counts, not task titles or descriptions. The Doubt
Solver also sends the submitted subject, study level, and optional context. Do
not configure a provider unless that data sharing is appropriate for you. AI
output is a learning aid; verify important answers with course materials.
The Study-time coach sends account-scoped daily focus totals and subject summaries
for the last 30 days only when that mode is selected. To improve exam alignment,
include the relevant grade / degree, exam, board, university, or syllabus in chat.
The AI Planner also sends your goal, subject, deadline, study level, and
availability to the configured provider. It creates only a draft first; sessions
are added to the task database only after you select “Approve and add tasks”.
AI provider requests have a 30-second timeout, prompt and response size limits,
and bounded completion length. Provider error responses are reduced to a status
message rather than exposing raw response bodies.

## API

- `GET /api/health` to check database readiness and optional AI configuration
- `POST /api/auth/register` and `POST /api/auth/login` when hosted accounts are enabled
- `GET /api/auth/me` and `POST /api/auth/logout` for browser session state
- `GET /api/tasks?status=all|open|completed&page=1&page_size=50`
- `POST /api/tasks`
- `PATCH /api/tasks/{id}`
- `DELETE /api/tasks/{id}`
- `GET /api/progress`
- `GET /api/study-sessions?limit=20`
- `GET /api/exports/tasks.csv` to download all tasks as CSV
- `GET /api/exports/backup.json` to download tasks and focus-session history as JSON
- `POST /api/imports/backup` to add tasks and focus-session history from a JSON backup
- `POST /api/study-sessions` to save a completed focus session
- `POST /api/progress/analyze` for an AI-assisted review of aggregate study progress
- `GET /api/deadlines?days=7`
- `GET /api/plan?days=7`
- `POST /api/assistant` with `{"message": "What should I study next?"}`
- `GET /api/ai/status`
- `POST /api/doubts/solve` with a subject, question, and optional level/context
- `POST /api/plans/generate` to generate a reviewable study-plan draft
- `POST /api/plans/approve` to add approved draft sessions as tasks

The Doubt Solver returns `answer`, `steps`, `concepts`, `analysis`, `difficulty`,
`misconception`, and `follow_up`. It responds with HTTP 503 when no AI provider is
configured and HTTP 502 if the configured provider request or response fails.

Interactive API documentation is available at <http://127.0.0.1:8000/docs>.
The task-list response includes `items`, `total`, `page`, `page_size`, and `pages`.

## Tests

```powershell
python -m pytest
```

Install the development check tools with `python -m pip install -r requirements-dev.txt`.
The GitHub Actions workflow runs Ruff, Python compilation checks, the test suite,
and a dependency vulnerability audit on Python 3.10 and 3.13.

See [architecture](docs/architecture.md), [workflow](docs/workflow.md), and
[demo script](docs/demo_script.md) for project details.
