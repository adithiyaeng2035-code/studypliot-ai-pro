# Release and recovery guide

## Before a release

1. Take a database snapshot using the managed PostgreSQL provider or SQLite's
   online backup facility.
2. Download a StudyPilot JSON backup from **Your data → Export & backup**. It
   includes tasks, task resource links, recurrence details, and focus-session
   history for the signed-in account.
3. Deploy the candidate to a preview environment connected to a separate
   database. Check `/api/health`, sign-in, task creation, resource links, plan
   review, calendar export, and backup restore.
4. Apply the release to production. Ordered migrations run at application
   startup. Keep the database snapshot until the release is accepted.

## Container deployment

Build the image with `docker build -t studypilot:latest .`. For a persistent
single-user local deployment, run it with a named volume:

```sh
docker volume create studypilot-data
docker run --detach --name studypilot --restart unless-stopped \
  --publish 127.0.0.1:8000:8000 \
  --volume studypilot-data:/data \
  studypilot:latest
```

For public hosting, place the container behind an HTTPS reverse proxy and set
`DATABASE_URL`, `AUTH_ENABLED=true`, `AUTH_COOKIE_SECURE=true`, and the desired
`AUTH_ALLOW_REGISTRATION` value through the host's secret manager. Use managed
PostgreSQL for multi-instance hosting; a local container volume is not a
shared database. Configure optional `LLM_BASE_URL`, `LLM_API_KEY`, and
`LLM_MODEL` only when AI features are desired.

## Restore

- For account-level recovery, sign in and use **Your data → Choose JSON backup
  → Restore backup**. Restore is additive, so check for duplicate records if a
  backup was imported previously.
- Task CSV files can also be imported from **Your data**. CSV import adds rows
  without replacing current data and preserves task completion, recurrence, and
  resource-link columns included by StudyPilot's CSV export.
- For full database recovery, use the provider's restore procedure or restore
  the SQLite database snapshot while the application is stopped. Restart the
  app and verify `/api/health` and a signed-in user's task list.
- Keep the encryption and access controls of database snapshots equivalent to
  the live database. A StudyPilot JSON backup contains personal study records.

## Operational notes

- Never place credentials in the image, repository, or a browser-visible
  variable. Use deployment secrets and rotate exposed credentials.
- Keep at least one recent database snapshot and periodically confirm that it
  can be restored in a non-production environment.
- SQLite is suitable for a single local instance. Use PostgreSQL for hosted
  accounts, concurrent writes, or horizontally scaled deployment.
- The health endpoint checks database connectivity. AI configuration is
  reported as optional and is not required for core task management.
