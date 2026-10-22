# StudyPilot AI Pro — Projected Upgrade Roadmap

**Planning horizon:** 10–14 weeks  
**Estimate basis:** One developer building on the current FastAPI, SQLite/PostgreSQL, and JavaScript application. Estimates are directional and should be revisited before scheduling.

## Project vision

Grow StudyPilot from a local-first study planner into a dependable, private, and accessible study platform. The roadmap first strengthens data reliability, then supports multiple students, and finally expands planning, progress, and deployment capabilities.

## Phase 1 — Reliability and data protection

**Projected duration: 2–3 weeks**

| Upgrade | Scope | Expected result |
| --- | --- | --- |
| Versioned database migrations | Track and apply schema changes for SQLite and PostgreSQL; preserve existing user data. | Database changes become repeatable and safer to release. |
| Backup and restore | Validate backup files, support restore, and document a dependable backup routine. | Users can recover study data after a mistake or system issue. |
| AI request safeguards — implemented | Validate provider URLs, cap prompt and response sizes and completion length, enforce request timeout, and return safe provider errors. | AI features fail more predictably and handle oversized requests more safely. |
| Operational visibility — implemented | Emit JSON request logs and check database readiness; report optional AI configuration without treating it as required. | Configuration and runtime issues are easier to diagnose without logging prompt contents or database errors to users. |
| Automated project checks — implemented | Run Ruff, compilation checks, tests, an OpenAPI route-contract check, and a dependency audit in GitHub Actions on Python 3.10 and 3.13. | Regressions and known dependency vulnerabilities are surfaced earlier. |

**Phase outcome:** A sturdier foundation for new features and deployment.

## Phase 2 — Accounts and secure access

**Projected duration: 2–3 weeks**

| Upgrade | Scope | Expected result |
| --- | --- | --- |
| User accounts — baseline implemented | Add sign-up, sign-in, and sign-out with a bootstrap token for the first account. | Students can access their own StudyPilot account. |
| Private study data — implemented | Associate tasks, focus sessions, plans, progress, and exports with the correct account. | Student records remain separated. |
| Session and access protections — baseline implemented | Use Argon2 password hashes, expiring server-side sessions, HttpOnly cookies, CSRF checks, and sign-in throttling. | Account data is protected across app and API usage. |
| Privacy controls - baseline implemented | Explain AI data sharing; provide account-scoped data export and password-confirmed account/data deletion. | Students have clearer control over their information. |

**Phase outcome:** The app can support multiple students with separate data.

## Phase 3 — Planning and reminders

**Projected duration: 2–3 weeks**

| Upgrade | Scope | Expected result |
| --- | --- | --- |
| Calendar view - implemented | Display tasks and study sessions by week and month, with account-scoped data. | Students can see workload and deadlines at a glance. |
| Recurring tasks - implemented | Support daily, weekly, or monthly tasks through a chosen end date; completing an occurrence creates the next one, and removing a recurring task removes the series. | Regular commitments are easier to manage. |
| Reminders | Add configurable in-app reminders and calendar exports. | Important deadlines are less likely to be missed. |
| Workload-aware study plans | Consider deadlines, availability, estimated effort, and existing plans. | Draft plans fit the student's actual schedule better. |
| Plan adjustments | Allow editing and rescheduling before approving a plan. | Students remain in control of generated schedules. |

**Phase outcome:** StudyPilot plans around a student's real schedule and helps them follow through.

## Phase 4 — Learning and progress features

**Projected duration: 2–3 weeks**

| Upgrade | Scope | Expected result |
| --- | --- | --- |
| Progress trends | Track task completion, focus time, and subject balance over time. | Students can recognize changes in their study habits. |
| All-subject Doubt Solver for school through M.Tech | Strengthen the existing open-subject Doubt Solver for school learners, B.Tech, M.Tech, and other study programs. Cover mathematics, sciences, engineering branches, computing, languages, humanities, business, and other subjects. Adapt terminology, depth, notation, and examples to the student's level. | Students can ask questions in any subject and get an appropriately leveled explanation, reasoning steps, key concepts, and a check-for-understanding prompt. |
| Study notes and resources | Attach notes, links, and learning materials to tasks. | Relevant context stays close to each assignment. |
| Evidence-based progress reviews | Use trend data to suggest next steps and show supporting evidence. | Recommendations are more useful and easier to evaluate. |
| Optional goals and streaks | Add weekly targets and simple progress indicators. | Students can build consistent routines at their own pace. |

**Phase outcome:** Students can understand their progress, get guided explanations across subjects, and choose what to work on next.

## Phase 5 — Usability and release readiness

**Projected duration: 2–3 weeks**

| Upgrade | Scope | Expected result |
| --- | --- | --- |
| Mobile-friendly experience | Refine layouts and controls for phones and tablets. | Core study workflows work on smaller screens. |
| Accessibility improvements | Improve keyboard navigation, screen-reader labels, contrast, and form feedback. | More students can use the app comfortably. |
| Data import and export | Import tasks and export selected data in common formats. | Students can move their information into and out of StudyPilot. |
| Deployment setup | Provide production configuration, container packaging, and a deployment guide. | Hosting the app becomes more repeatable. |
| Release and recovery guide | Document upgrades, backups, configuration, and recovery steps. | Operators have a clear path for maintenance and recovery. |

**Phase outcome:** A more polished app that is easier to use, deploy, and maintain.

## Suggested milestone sequence

1. **Foundation release:** migrations, backup and restore, AI safeguards, operational visibility, automated checks.
2. **Multi-user release:** accounts, private data, access protections, and privacy controls.
3. **Planning release:** calendar, recurring tasks, reminders, and workload-aware plan revisions.
4. **Learning insights release:** progress trends, study resources, and evidence-based reviews.
5. **Public release readiness:** accessibility, mobile refinement, data portability, and deployment documentation.

## First milestone recommendation

Begin with **versioned database migrations**, **backup and restore**, **AI request safeguards**, and **automated project checks**. Complete those before adding accounts or opening the app to multiple users. This sequence reduces data and maintenance risks while keeping the first milestone focused.

## Planning assumptions

- Estimates assume one developer familiar with the existing codebase.
- Authentication, deployment, and calendar integrations can expand the schedule depending on provider choices and hosting requirements.
- Each milestone should be reviewed against student feedback before the next phase is committed.
- The roadmap is a projection; timelines should be updated after the first milestone is scoped and implemented.
