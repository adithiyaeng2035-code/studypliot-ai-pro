const taskList = document.querySelector("#task-list");
const notice = document.querySelector("#notice");
const filter = document.querySelector("#task-filter");
const taskPageSummary = document.querySelector("#task-page-summary");
const previousPage = document.querySelector("#previous-page");
const nextPage = document.querySelector("#next-page");
const taskSearch = document.querySelector("#task-search");
const taskSubjectFilter = document.querySelector("#task-subject-filter");
let currentPage = 1;
let taskFilterTimer = null;
let calendarAnchor = new Date();
let calendarView = "week";

function localDateKey(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function calendarStart() {
  const date = new Date(calendarAnchor.getFullYear(), calendarAnchor.getMonth(), calendarAnchor.getDate());
  if (calendarView === "month") {
    date.setDate(1);
    date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  } else {
    date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  }
  return date;
}

function calendarDateLabel(start, days) {
  if (calendarView === "month") {
    return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" })
      .format(new Date(calendarAnchor.getFullYear(), calendarAnchor.getMonth(), 1));
  }
  const end = new Date(start);
  end.setDate(end.getDate() + days - 1);
  return `${new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(start)} – ${new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(end)}`;
}

async function loadCalendar() {
  const start = calendarStart();
  const days = calendarView === "month" ? 42 : 7;
  const startKey = localDateKey(start);
  const events = await api(`/calendar?start=${startKey}&days=${days}`);
  const taskMap = new Map();
  const sessionMap = new Map();
  for (const task of events.tasks) {
    if (!taskMap.has(task.due_date)) taskMap.set(task.due_date, []);
    taskMap.get(task.due_date).push(task);
  }
  for (const session of events.study_sessions) {
    const key = localDateKey(new Date(session.started_at));
    if (!sessionMap.has(key)) sessionMap.set(key, []);
    sessionMap.get(key).push(session);
  }
  document.querySelector("#calendar-period").textContent = calendarDateLabel(start, days);
  const today = localDateKey(new Date());
  const cells = [];
  for (let offset = 0; offset < days; offset += 1) {
    const day = new Date(start);
    day.setDate(day.getDate() + offset);
    const key = localDateKey(day);
    const inMonth = day.getMonth() === calendarAnchor.getMonth();
    const tasks = taskMap.get(key) || [];
    const sessions = sessionMap.get(key) || [];
    const items = [
      ...tasks.map((task) => `<div class="calendar-event calendar-task ${task.completed ? "is-complete" : ""}" title="${escapeHtml(task.title)} · ${escapeHtml(task.subject)}">${escapeHtml(task.title)}</div>`),
      ...sessions.map((session) => `<div class="calendar-event calendar-session" title="${escapeHtml(session.subject)} · ${session.duration_minutes} minutes">${escapeHtml(session.subject)} · ${session.duration_minutes}m</div>`),
    ];
    cells.push(`<article class="calendar-day ${calendarView === "month" && !inMonth ? "outside-month" : ""} ${key === today ? "is-today" : ""}"><time datetime="${key}">${day.getDate()}</time><div class="calendar-events">${items.join("")}</div></article>`);
  }
  document.querySelector("#calendar-grid").innerHTML = cells.join("");
  document.querySelector("#calendar-grid").classList.toggle("month-view", calendarView === "month");
  const toggle = document.querySelector("#calendar-view-toggle");
  toggle.textContent = calendarView === "week" ? "Month" : "Week";
  toggle.setAttribute("aria-pressed", String(calendarView === "month"));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

async function api(path, options = {}) {
  const response = await window.studyPilotFetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Keep the HTTP status message when the server did not return JSON.
    }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function showNotice(message) {
  notice.textContent = message;
  notice.hidden = !message;
}

function formatDate(value, options = { month: "short", day: "numeric" }) {
  if (!value) return "No due date";
  return new Intl.DateTimeFormat(undefined, options).format(new Date(`${value}T12:00:00`));
}

function recurrenceLabel(task) {
  const labels = { daily: "Daily", weekly: "Weekly", monthly: "Monthly" };
  return labels[task.recurrence_rule] || "";
}

async function loadProgress() {
  const progress = await api("/progress");
  document.querySelector("#completed-count").textContent = progress.completed_tasks;
  document.querySelector("#open-count").textContent = progress.open_tasks;
  document.querySelector("#minutes-count").textContent = progress.focus_minutes;
  document.querySelector("#completion-rate").textContent = progress.completion_percent;
  document.querySelector("#completion-caption").textContent =
    `${progress.completed_tasks} of ${progress.total_tasks} tasks finished`;
  document.querySelector("#focus-minutes-caption").textContent =
    `${progress.focus_sessions} focus session(s) saved`;
}

const focusGoalSelect = document.querySelector("#focus-goal-target");
const focusGoalProgress = document.querySelector("#focus-goal-progress");
const focusGoalToday = document.querySelector("#focus-goal-today");
const focusGoalStatus = document.querySelector("#focus-goal-status");
const focusWeekChart = document.querySelector("#focus-week-chart");
let focusGoalMinutes = 60;
let focusGoalSessionsByDay = new Map();
let focusGoalTodayKey = localDateKey(new Date());
let focusGoalWeekKeys = [];

function focusGoalStorageKey() {
  const account = document.querySelector("#account-email").textContent.trim().toLowerCase() || "local";
  return `studypilot:${account}:daily-focus-goal`;
}

function renderFocusGoal() {
  const todayMinutes = focusGoalSessionsByDay.get(focusGoalTodayKey) || 0;
  focusGoalProgress.max = focusGoalMinutes;
  focusGoalProgress.value = Math.min(todayMinutes, focusGoalMinutes);
  focusGoalProgress.setAttribute("aria-label", `Today's focus goal: ${todayMinutes} of ${focusGoalMinutes} minutes`);
  focusGoalToday.textContent = `${todayMinutes} / ${focusGoalMinutes} min`;
  focusGoalStatus.textContent = todayMinutes >= focusGoalMinutes
    ? "Daily goal reached. Great work."
    : `${focusGoalMinutes - todayMinutes} minutes to go today`;

  focusWeekChart.replaceChildren();
  for (const key of focusGoalWeekKeys) {
    const day = new Date(`${key}T12:00:00`);
    const minutes = focusGoalSessionsByDay.get(key) || 0;
    const column = document.createElement("div");
    column.className = `focus-week-day${key === focusGoalTodayKey ? " is-today" : ""}`;
    column.setAttribute("role", "img");
    column.setAttribute("aria-label", `${new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(day)}: ${minutes} focus minutes`);
    const amount = document.createElement("span");
    amount.className = "focus-week-minutes";
    amount.textContent = `${minutes}m`;
    const track = document.createElement("span");
    track.className = "focus-week-track";
    const bar = document.createElement("span");
    bar.style.height = `${minutes ? Math.max(5, Math.min(100, (minutes / focusGoalMinutes) * 100)) : 3}%`;
    track.append(bar);
    const label = document.createElement("span");
    label.className = "focus-week-label";
    label.textContent = new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(day);
    column.append(amount, track, label);
    focusWeekChart.append(column);
  }
}

async function loadFocusGoal() {
  try {
    if (!(await window.studyPilotAuthReady)) return;
    const savedGoal = Number(localStorage.getItem(focusGoalStorageKey()));
    if ([30, 45, 60, 90, 120, 180].includes(savedGoal)) focusGoalMinutes = savedGoal;
    focusGoalSelect.value = String(focusGoalMinutes);

    const today = new Date();
    focusGoalTodayKey = localDateKey(today);
    const firstDay = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6);
    focusGoalWeekKeys = Array.from({ length: 7 }, (_, index) => {
      const day = new Date(firstDay);
      day.setDate(firstDay.getDate() + index);
      return localDateKey(day);
    });
    const events = await api(`/calendar?start=${focusGoalWeekKeys[0]}&days=7`);
    focusGoalSessionsByDay = new Map();
    for (const session of events.study_sessions) {
      const key = localDateKey(new Date(session.started_at));
      if (focusGoalWeekKeys.includes(key)) {
        focusGoalSessionsByDay.set(key, (focusGoalSessionsByDay.get(key) || 0) + Number(session.duration_minutes));
      }
    }
    renderFocusGoal();
  } catch (error) {
    focusGoalStatus.textContent = `Couldn't load focus goal: ${error.message}`;
  }
}

focusGoalSelect.addEventListener("change", async () => {
  focusGoalMinutes = Number(focusGoalSelect.value);
  try {
    await window.studyPilotAuthReady;
    localStorage.setItem(focusGoalStorageKey(), String(focusGoalMinutes));
  } catch {
    // Keep the selected goal for this page even when browser storage is unavailable.
  }
  renderFocusGoal();
});

function renderInsightList(selector, values) {
  const list = document.querySelector(selector);
  list.replaceChildren();
  for (const value of values) {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  }
}

async function checkProgressModel() {
  const status = document.querySelector("#progress-insight-status");
  try {
    const provider = await api("/ai/status");
    if (!provider.configured) {
      status.textContent =
        "AI analysis is unavailable until LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL are configured and StudyPilot is restarted.";
    }
  } catch (error) {
    status.textContent = `Couldn't check AI setup: ${error.message}`;
  }
}

const focusForm = document.querySelector("#focus-form");
const focusTaskSelect = document.querySelector("#focus-task");
const focusClock = document.querySelector("#focus-clock");
const focusStatus = document.querySelector("#focus-status");
const focusStartButton = document.querySelector("#focus-start");
const focusPauseButton = document.querySelector("#focus-pause");
const focusFinishButton = document.querySelector("#focus-finish");
let focusTimer = null;
let focusTicker = null;

function selectedFocusMinutes() {
  return Number(focusForm.elements.duration_minutes.value);
}

function renderFocusClock(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  focusClock.textContent = `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function focusRemainingSeconds() {
  if (!focusTimer) return selectedFocusMinutes() * 60;
  if (focusTimer.pausedAt !== null) return focusTimer.remainingSeconds;
  return Math.max(0, Math.ceil((focusTimer.endsAt - Date.now()) / 1000));
}

function updateFocusClock() {
  const remaining = focusRemainingSeconds();
  renderFocusClock(remaining);
  if (remaining === 0 && focusTimer && !focusTimer.pausedAt && !focusTimer.saving) {
    finishFocusSession();
  }
}

async function loadFocusTasks() {
  const result = await api("/tasks?status=open&page=1&page_size=100");
  focusTaskSelect.replaceChildren(new Option("No linked task", ""));
  for (const task of result.items) {
    focusTaskSelect.add(new Option(`${task.subject}: ${task.title}`, String(task.id)));
  }
}

async function loadFocusHistory() {
  const { items, total_sessions, total_minutes } = await api("/study-sessions?limit=8");
  const list = document.querySelector("#focus-history-list");
  document.querySelector("#focus-history-summary").textContent =
    `${total_sessions} session(s) · ${total_minutes} focus minutes total`;
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No completed focus sessions yet.";
    list.append(empty);
    return;
  }
  for (const session of items) {
    const item = document.createElement("li");
    item.className = "focus-history-item";
    const details = document.createElement("span");
    details.textContent = `${session.subject} · ${session.duration_minutes} min` +
      (session.task_title ? ` · ${session.task_title}` : "");
    const time = document.createElement("time");
    time.dateTime = session.completed_at;
    time.textContent = new Intl.DateTimeFormat(undefined, {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    }).format(new Date(session.completed_at));
    item.append(details, time);
    list.append(item);
  }
}

async function finishFocusSession() {
  if (!focusTimer) return;
  window.clearInterval(focusTicker);
  focusTicker = null;
  const endedAt = new Date();
  const activeMilliseconds = focusTimer.activeMilliseconds +
    (focusTimer.pausedAt === null ? Date.now() - focusTimer.segmentStartedAt : 0);
  const elapsedMinutes = Math.ceil(activeMilliseconds / 60000);
  if (elapsedMinutes < 1) {
    focusStatus.textContent = "Study for at least one minute before saving a session.";
    focusTimer = null;
    focusPauseButton.disabled = true;
    focusFinishButton.disabled = true;
    focusStartButton.disabled = false;
    renderFocusClock(selectedFocusMinutes() * 60);
    return;
  }

  focusPauseButton.disabled = true;
  focusFinishButton.disabled = true;
  focusStatus.textContent = "Saving your study session…";
  focusTimer.saving = true;
  const values = Object.fromEntries(new FormData(focusForm));
  let session;
  try {
    session = await api("/study-sessions", {
      method: "POST",
      body: JSON.stringify({
        task_id: values.task_id ? Number(values.task_id) : null,
        subject: values.subject,
        duration_minutes: Math.min(elapsedMinutes, 240),
        notes: values.notes,
        started_at: focusTimer.startedAt.toISOString(),
        completed_at: endedAt.toISOString(),
      }),
    });
  } catch (error) {
    focusStatus.textContent = `Couldn't save the study session: ${error.message}`;
    focusTimer.saving = false;
    focusPauseButton.disabled = false;
    focusFinishButton.disabled = false;
    if (focusTimer.pausedAt === null && focusRemainingSeconds() > 0) {
      focusTicker = window.setInterval(updateFocusClock, 250);
    }
    return;
  }

  focusStatus.textContent = `Saved ${session.duration_minutes} minute(s) of ${session.subject} study.`;
  focusTimer = null;
  focusStartButton.disabled = false;
  renderFocusClock(selectedFocusMinutes() * 60);
  try {
    await Promise.all([loadFocusHistory(), loadProgress(), loadCalendar(), loadFocusGoal()]);
  } catch (error) {
    focusStatus.textContent = `Session saved, but dashboard refresh failed: ${error.message}`;
  }
}

focusForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (focusTimer || !focusForm.reportValidity()) return;
  focusTimer = {
    startedAt: new Date(),
    segmentStartedAt: Date.now(),
    activeMilliseconds: 0,
    endsAt: Date.now() + selectedFocusMinutes() * 60 * 1000,
    remainingSeconds: selectedFocusMinutes() * 60,
    pausedAt: null,
  };
  focusStartButton.disabled = true;
  focusPauseButton.disabled = false;
  focusFinishButton.disabled = false;
  focusStatus.textContent = "Focus session running. You can pause or finish early and save.";
  focusTicker = window.setInterval(updateFocusClock, 250);
  updateFocusClock();
});

focusPauseButton.addEventListener("click", () => {
  if (!focusTimer) return;
  if (focusTimer.pausedAt === null) {
    focusTimer.remainingSeconds = focusRemainingSeconds();
    focusTimer.activeMilliseconds += Date.now() - focusTimer.segmentStartedAt;
    focusTimer.pausedAt = Date.now();
    focusPauseButton.textContent = "Resume";
    focusStatus.textContent = "Session paused.";
  } else {
    focusTimer.endsAt = Date.now() + focusTimer.remainingSeconds * 1000;
    focusTimer.segmentStartedAt = Date.now();
    focusTimer.pausedAt = null;
    focusPauseButton.textContent = "Pause";
    focusStatus.textContent = "Focus session running.";
  }
  updateFocusClock();
});

focusFinishButton.addEventListener("click", finishFocusSession);
focusForm.elements.duration_minutes.addEventListener("input", () => {
  if (!focusTimer) renderFocusClock(selectedFocusMinutes() * 60);
});

document.querySelector("#analyze-progress").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const status = document.querySelector("#progress-insight-status");
  const resultPanel = document.querySelector("#progress-insight-result");
  button.disabled = true;
  status.textContent = "Reviewing your study progress…";
  resultPanel.hidden = true;
  try {
    const result = await api("/progress/analyze", { method: "POST", body: "{}" });
    const analysis = result.analysis;
    document.querySelector("#progress-insight-summary").textContent = analysis.summary;
    renderInsightList("#progress-insight-strengths", analysis.strengths);
    renderInsightList("#progress-insight-focus", analysis.focus_areas);

    const recommendations = document.querySelector("#progress-insight-recommendations");
    recommendations.replaceChildren();
    for (const recommendation of analysis.recommendations) {
      const card = document.createElement("article");
      const title = document.createElement("h4");
      title.textContent = recommendation.title;
      const reason = document.createElement("p");
      reason.textContent = recommendation.reason;
      const action = document.createElement("p");
      action.textContent = recommendation.action;
      card.append(title, reason, action);
      recommendations.append(card);
    }
    document.querySelector("#progress-insight-next-step").textContent = analysis.next_step;

    const evidence = result.evidence;
    document.querySelector("#progress-insight-evidence").textContent =
      `Based on ${evidence.progress.total_tasks} task(s), ${evidence.subject_progress.length} subject group(s), ` +
      `${evidence.tasks_completed_in_last_30_days} completion(s) in the last 30 days, and ` +
      `${evidence.overdue_open_tasks} overdue open task(s). As of ${evidence.as_of_date}.`;
    status.textContent = "Progress review complete.";
    resultPanel.hidden = false;
  } catch (error) {
    status.textContent = `Couldn't analyze progress: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#backup-restore-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.querySelector("#backup-file");
  const status = document.querySelector("#backup-restore-status");
  const file = fileInput.files[0];
  if (!file) return;
  if (file.size > 20 * 1024 * 1024) {
    status.textContent = "Backup files must be 20 MB or smaller.";
    return;
  }
  if (!window.confirm("Add the records in this backup to the current StudyPilot data? Existing records will stay. Importing the same backup twice creates duplicates.")) {
    return;
  }
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  status.textContent = "Validating and restoring backup…";
  try {
    const backup = JSON.parse(await file.text());
    const result = await api("/imports/backup", {
      method: "POST",
      body: JSON.stringify(backup),
    });
    status.textContent = `Restored ${result.tasks_added} task(s) and ${result.study_sessions_added} focus session(s).`;
    fileInput.value = "";
    await refresh();
    await loadFocusTasks();
    await loadFocusHistory();
  } catch (error) {
    status.textContent = `Backup restore failed: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});

async function loadTasks() {
  const parameters = new URLSearchParams({
    status: filter.value,
    page: String(currentPage),
    page_size: "50",
  });
  if (taskSearch.value.trim()) parameters.set("search", taskSearch.value.trim());
  if (taskSubjectFilter.value.trim()) parameters.set("subject", taskSubjectFilter.value.trim());
  const result = await api(`/tasks?${parameters.toString()}`);
  currentPage = result.page;
  taskPageSummary.textContent = result.total
    ? `Showing ${(result.page - 1) * result.page_size + 1}–${Math.min(result.page * result.page_size, result.total)} of ${result.total}`
    : "No tasks";
  previousPage.disabled = result.page <= 1;
  nextPage.disabled = result.page >= result.pages;
  const tasks = result.items;
  if (!tasks.length) {
    const hasTaskFilters = taskSearch.value.trim() || taskSubjectFilter.value.trim();
    const emptyMessage = hasTaskFilters
      ? "No tasks match those filters. Try a different search or subject."
      : filter.value === "completed" ? "No completed tasks yet." : "Nothing here yet. Add a task above to get started.";
    taskList.innerHTML = `<li class="empty-state">${emptyMessage}</li>`;
    return;
  }
  taskList.innerHTML = tasks.map((task) => `
    <li class="task-item ${task.completed ? "is-complete" : ""}">
      <input class="task-check" type="checkbox" data-action="complete" data-id="${task.id}"
        aria-label="Mark ${escapeHtml(task.title)} ${task.completed ? "incomplete" : "complete"}"
        ${task.completed ? "checked" : ""}>
      <div class="task-content">
        <div class="task-title">${escapeHtml(task.title)}</div>
        <div class="task-meta"><span>${escapeHtml(task.subject)}</span><span>${formatDate(task.due_date)}</span><span>${task.estimated_minutes} min</span>${recurrenceLabel(task) ? `<span>${recurrenceLabel(task)} · through ${formatDate(task.recurrence_until, { month: "short", day: "numeric", year: "numeric" })}</span>` : ""}</div>
        ${task.description ? `<p class="task-description">${escapeHtml(task.description)}</p>` : ""}
      </div>
      <button class="delete-button" type="button" data-action="delete" data-id="${task.id}" data-recurring="${task.recurrence_rule !== "none"}" aria-label="Delete ${escapeHtml(task.title)}">×</button>
    </li>`).join("");
}

async function loadPlan() {
  const plan = await api("/plan?days=7");
  const activeDays = plan.sessions.filter((session) => session.tasks.length);
  const planList = document.querySelector("#plan-list");
  if (!activeDays.length && !plan.unscheduled_count) {
    planList.innerHTML = '<p class="empty-state">Add a task to see your suggested study plan.</p>';
    return;
  }
  planList.innerHTML = activeDays.map((session) => `
    <div class="plan-day">
      <div class="plan-date">${formatDate(session.date, { weekday: "short", month: "short", day: "numeric" })}</div>
      ${session.tasks.map((task) => `<div class="plan-task"><span>${escapeHtml(task.title)}</span><span>${task.estimated_minutes}m</span></div>`).join("")}
      ${session.task_count > session.tasks.length ? `<div class="plan-overflow">Showing ${session.tasks.length} of ${session.task_count} tasks</div>` : ""}
    </div>`).join("") +
    (plan.unscheduled_count ? `<p class="empty-state">${plan.unscheduled_count} task(s) are due after this 7-day view.</p>` : "") +
    `<div class="plan-total">Planned this week <strong>${plan.total_minutes} minutes</strong></div>`;
}

async function loadDeadlines() {
  const result = await api("/deadlines?days=7");
  const deadlines = [
    ...result.overdue.map((task) => ({ ...task, overdue: true })),
    ...result.upcoming,
  ];
  const list = document.querySelector("#deadline-list");
  if (!deadlines.length) {
    list.innerHTML = '<p class="empty-state">No deadlines in the next 7 days. Enjoy the breathing room.</p>';
    return;
  }
  list.innerHTML = deadlines.map((task) => `
    <div class="deadline-item">
      <span class="deadline-marker ${task.overdue ? "overdue" : ""}"></span>
      <div class="deadline-copy"><strong>${escapeHtml(task.title)}</strong>
        <span>${task.overdue ? "Overdue" : `Due ${formatDate(task.due_date)}`} · ${escapeHtml(task.subject)}</span>
      </div>
    </div>`).join("") +
    (result.overdue_count > result.overdue.length
      ? `<p class="empty-state">${result.overdue_count - result.overdue.length} more overdue deadline(s) not shown.</p>` : "") +
    (result.upcoming_count > result.upcoming.length
      ? `<p class="empty-state">${result.upcoming_count - result.upcoming.length} more upcoming deadline(s) not shown.</p>` : "");
}

async function refresh() {
  showNotice("");
  try {
    await Promise.all([loadProgress(), loadTasks(), loadPlan(), loadDeadlines(), loadCalendar()]);
  } catch (error) {
    showNotice(`Couldn't load your study space: ${error.message}`);
  }
}

document.querySelector("#today-label").textContent =
  new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" }).format(new Date());

document.querySelector("#calendar-prev").addEventListener("click", () => {
  if (calendarView === "month") calendarAnchor.setMonth(calendarAnchor.getMonth() - 1, 1);
  else calendarAnchor.setDate(calendarAnchor.getDate() - 7);
  loadCalendar().catch((error) => showNotice(`Couldn't load calendar: ${error.message}`));
});

document.querySelector("#calendar-next").addEventListener("click", () => {
  if (calendarView === "month") calendarAnchor.setMonth(calendarAnchor.getMonth() + 1, 1);
  else calendarAnchor.setDate(calendarAnchor.getDate() + 7);
  loadCalendar().catch((error) => showNotice(`Couldn't load calendar: ${error.message}`));
});

document.querySelector("#calendar-view-toggle").addEventListener("click", () => {
  calendarView = calendarView === "week" ? "month" : "week";
  loadCalendar().catch((error) => showNotice(`Couldn't load calendar: ${error.message}`));
});

filter.addEventListener("change", () => {
  currentPage = 1;
  loadTasks().catch((error) => showNotice(error.message));
});

function scheduleTaskFilterUpdate() {
  window.clearTimeout(taskFilterTimer);
  currentPage = 1;
  taskFilterTimer = window.setTimeout(() => {
    loadTasks().catch((error) => showNotice(error.message));
  }, 250);
}

taskSearch.addEventListener("input", scheduleTaskFilterUpdate);
taskSubjectFilter.addEventListener("input", scheduleTaskFilterUpdate);

const recurrenceSelect = document.querySelector("#task-recurrence");
const recurrenceUntilLabel = document.querySelector("#recurrence-until-label");
const recurrenceUntilInput = recurrenceUntilLabel.querySelector("input");
const dueDateInput = document.querySelector('#task-form input[name="due_date"]');
recurrenceSelect.addEventListener("change", () => {
  const recurring = recurrenceSelect.value !== "none";
  recurrenceUntilLabel.hidden = !recurring;
  recurrenceUntilInput.disabled = !recurring;
  recurrenceUntilInput.required = recurring;
  dueDateInput.required = recurring;
});

previousPage.addEventListener("click", () => {
  if (currentPage > 1) currentPage -= 1;
  loadTasks().catch((error) => showNotice(error.message));
});

nextPage.addEventListener("click", () => {
  currentPage += 1;
  loadTasks().catch((error) => showNotice(error.message));
});

document.querySelector("#task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  values.estimated_minutes = Number(values.estimated_minutes);
  if (!values.subject.trim()) values.subject = "General";
  if (!values.due_date) values.due_date = null;
  if (!values.recurrence_until) values.recurrence_until = null;
  try {
    await api("/tasks", { method: "POST", body: JSON.stringify(values) });
    form.reset();
    recurrenceSelect.dispatchEvent(new Event("change"));
    form.elements.estimated_minutes.value = 30;
    currentPage = 1;
    await refresh();
  } catch (error) {
    showNotice(`Couldn't add task: ${error.message}`);
  }
});

taskList.addEventListener("change", async (event) => {
  const control = event.target.closest('[data-action="complete"]');
  if (!control) return;
  try {
    await api(`/tasks/${control.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({ completed: control.checked }),
    });
    await refresh();
  } catch (error) {
    control.checked = !control.checked;
    showNotice(`Couldn't update task: ${error.message}`);
  }
});

taskList.addEventListener("click", async (event) => {
  const button = event.target.closest('[data-action="delete"]');
  if (!button) return;
  if (button.dataset.recurring === "true" && !window.confirm("Delete this recurring task and all its generated occurrences?")) return;
  try {
    await api(`/tasks/${button.dataset.id}`, { method: "DELETE" });
    await refresh();
  } catch (error) {
    showNotice(`Couldn't delete task: ${error.message}`);
  }
});

document.querySelector("#assistant-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = form.querySelector("button");
  const reply = document.querySelector("#assistant-reply");
  submit.disabled = true;
  reply.textContent = "Thinking…";
  try {
    const result = await api("/assistant", {
      method: "POST",
      body: JSON.stringify({ message: form.elements.message.value }),
    });
    reply.textContent = `${result.reply}${result.ai_enabled ? "" : " (Local suggestion)"}`;
    form.reset();
  } catch (error) {
    reply.textContent = `Couldn't get a suggestion: ${error.message}`;
  } finally {
    submit.disabled = false;
  }
});

checkProgressModel();
loadFocusGoal();
loadFocusTasks().catch((error) => {
  focusStatus.textContent = `Couldn't load tasks: ${error.message}`;
});
loadFocusHistory().catch((error) => {
  focusStatus.textContent = `Couldn't load session history: ${error.message}`;
});
refresh();
