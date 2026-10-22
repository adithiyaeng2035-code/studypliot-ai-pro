# Workflow

1. Start the server with `python -m app.main` and open `http://127.0.0.1:8000`.
2. Add a task with its subject, due date, and estimated study time.
3. Review the seven-day plan and upcoming deadline list.
4. Start a focus timer for a subject, optionally link an open task, and save the
   session when you finish. Completed sessions appear in recent session history.
5. Mark tasks complete as you study; progress statistics update automatically.
6. Use Progress insights to request an AI review of aggregate completion,
   subject, focus-session, and deadline evidence. Follow the suggested next
   step, then use the AI Study Planner to create a draft for review.
7. Use the StudyPilot prompt for a local suggestion, or configure an
   OpenAI-compatible provider for conversational answers and subject explanations.
8. On the AI Study Planner page, enter a goal, subject, deadline, and study
   availability. Review the model-generated session draft, then explicitly
   approve it to add each session as a task. Discarding the draft makes no
   database changes.

The plan groups incomplete tasks by due date. Tasks without a due date are placed
on today's plan, overdue tasks are also placed today, and tasks due after the
selected planning window are counted as unscheduled. To keep large datasets
responsive, each plan day displays up to 25 tasks while retaining complete task
counts and study-time totals.
