# StudyPilot AI Pro: roadmap delivery

The roadmap items below are now implemented in the repository. Most are
foundational implementations that can be extended using student feedback.

## Phase 1: Reliability and data protection

| Upgrade | Delivery |
| --- | --- |
| Versioned database migrations | Ordered SQLite and PostgreSQL migrations preserve existing records. Migration `006_task_resources` adds task resource links. |
| Backup and restore | Validated, additive, account-scoped JSON backup/restore covers tasks, recurrence, task resource links, and focus sessions. |
| AI request safeguards | Provider URLs, prompt and response sizes, output length, timeout, and safe provider errors are bounded. |
| Operational visibility | JSON request logs and database readiness endpoint avoid logging request bodies or exposing database errors. |
| Automated checks | GitHub Actions runs lint, compile, tests, OpenAPI contract checks, and dependency audits on Python 3.12 and 3.13. |

## Phase 2: Accounts and secure access

| Upgrade | Delivery |
| --- | --- |
| User accounts and private study data | Registration, sign-in, account-scoped tasks and sessions, and ownership-aware exports. |
| Session and access protections | Argon2 password hashing, expiring server-side sessions, HttpOnly cookies, CSRF checks, and sign-in throttling. |
| Privacy controls | AI data-sharing notices, account export, and password-confirmed permanent account deletion. |

## Phase 3: Planning and reminders

| Upgrade | Delivery |
| --- | --- |
| Calendar and calendar export | Week/month task and session calendar plus `.ics` download for dated tasks and focus sessions. |
| Recurring tasks | Daily, weekly, and monthly task series through a chosen end date. |
| Reminders | Optional browser notifications and an in-app due/overdue list, with 1, 3, or 7 day reminder windows. Notifications are delivered while the dashboard is open. |
| Workload-aware study plans | AI plan requests include account-scoped open task counts and estimated minutes grouped by due date. |
| Plan adjustments | Reviewers can edit dates, titles, notes, and effort, and add or remove sessions before approval. The server validates the final draft again. |

## Phase 4: Learning and progress

| Upgrade | Delivery |
| --- | --- |
| Progress trends | Account-scoped daily task completions, subject balance, and focus minutes for 7, 30, or 90 days, plus a current activity streak. |
| Cross-subject Doubt Solver | The existing solver accepts subjects and study levels broadly, including school, B.Tech, and M.Tech; provides reasoning, concepts, likely misconceptions, and a check-for-understanding prompt. |
| Study notes and resources | Task descriptions hold study notes and each task can link to an HTTP(S) resource. Both are included in exports and backups. |
| Evidence-based reviews | Progress reviews use aggregate task, deadline, subject, and focus-session evidence. |
| Optional goals | Daily focus-time target and seven-day activity chart; settings remain a local browser preference associated with the account. |

## Phase 5: Usability and release readiness

| Upgrade | Delivery |
| --- | --- |
| Mobile-friendly experience | Responsive dashboard, task, planner, and calendar layouts with touch-sized controls. |
| Accessibility improvements | Semantic landmarks, labeled controls, keyboard-visible focus, status announcements, and chart summaries. |
| Data import and export | Task CSV import/export, complete JSON backup/restore, and calendar `.ics` export. |
| Deployment setup | Vercel/PostgreSQL deployment instructions and a non-root Docker image with a persistent data volume and health check. |
| Release and recovery guide | Backup, release, container, restore, and operational guidance in `docs/release_recovery.md`. |

## Planning notes

The AI provider is optional for task management, reminders, progress history,
and resource links. Browser notifications require browser permission and an
open StudyPilot dashboard. For hosted, multi-user or multi-instance use, enable
authentication, use HTTPS and managed PostgreSQL, and keep database snapshots
outside the application host.
