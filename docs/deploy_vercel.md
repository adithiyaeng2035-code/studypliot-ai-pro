# Deploy StudyPilot on Vercel

Vercel runs this FastAPI application as a Python Function. The project entrypoint
is configured in `pyproject.toml`, and `.python-version` selects Python 3.12.

## Before publishing

StudyPilot's default SQLite database is unsuitable for Vercel's ephemeral
function filesystem. Create a managed PostgreSQL database with a provider of
your choice and keep its connection URL private. Configure the following
environment variables in the Vercel project for **Production** and Preview as
appropriate:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Private PostgreSQL connection URL from your database provider |
| `AUTH_ENABLED` | `true` |
| `AUTH_BOOTSTRAP_TOKEN` | A long, randomly generated secret; keep it out of source control |
| `AUTH_ALLOW_REGISTRATION` | `true` while users may create accounts; set to `false` to close registration later |
| `AUTH_COOKIE_SECURE` | `true` |

AI features are optional. To enable them, set `LLM_BASE_URL`, `LLM_API_KEY`, and
`LLM_MODEL` as encrypted Vercel environment variables. Do not put secrets in
this repository or expose them in a `NEXT_PUBLIC_` variable.

## Publish

1. Push this project to a Git provider supported by Vercel, or use the Vercel
   CLI from the project root.
2. Import the repository at <https://vercel.com/new> (or link the folder with
   `vercel link`).
3. Add the environment variables above in the Vercel project settings. Do not
   make a production deployment before PostgreSQL and authentication are set.
4. Deploy a Preview first and check the home page, `/api/health`, registration,
   sign-in, and task persistence across requests.
5. Deploy to Production and open the URL Vercel assigns. Enter the bootstrap
   token on the registration page only when creating the first account. After
   the first account is created, remove `AUTH_BOOTSTRAP_TOKEN` from Vercel if
   you do not need it; leave registration enabled only if new signups are
   intended.

Vercel deployment instructions can change; see the official
[FastAPI deployment guide](https://vercel.com/docs/frameworks/backend/fastapi)
and [Python runtime reference](https://vercel.com/docs/functions/runtimes/python).
