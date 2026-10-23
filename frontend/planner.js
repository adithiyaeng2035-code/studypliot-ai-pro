const plannerForm = document.querySelector("#planner-form");
const providerNotice = document.querySelector("#provider-notice");
const plannerNotice = document.querySelector("#planner-notice");
const draftPanel = document.querySelector("#draft-panel");
const sessionContainer = document.querySelector("#draft-sessions");
let currentDraft = null;

async function checkProvider() {
  try {
    const response = await window.studyPilotFetch("/api/ai/status");
    if (!response.ok) throw new Error(`Status check failed (${response.status})`);
    const result = await response.json();
    if (!result.configured) {
      providerNotice.hidden = false;
      providerNotice.textContent =
        "AI planning requires a configured model. Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in the same environment used to start StudyPilot, then restart the app.";
    }
  } catch (error) {
    providerNotice.hidden = false;
    providerNotice.textContent = `Could not check AI setup: ${error.message}`;
  }
}

function showNotice(message) {
  plannerNotice.textContent = message;
  plannerNotice.hidden = !message;
}

function renderDraft(plan) {
  currentDraft = plan;
  document.querySelector("#draft-goal").textContent = plan.goal;
  document.querySelector("#draft-summary").textContent =
    `${plan.subject} · ${plan.sessions.length} sessions · ${plan.start_date} through ${plan.deadline}`;
  sessionContainer.replaceChildren();

  plan.sessions.forEach((session, index) => {
    const card = document.createElement("article");
    card.className = "draft-session";
    const heading = document.createElement("strong");
    heading.className = "draft-session-date";
    heading.textContent = `Session ${index + 1}`;
    card.append(heading);
    const fields = [
      ["date", "Date", "date", session.date],
      ["title", "Session title", "text", session.title],
      ["description", "Notes", "text", session.description],
      ["estimated_minutes", "Minutes", "number", session.estimated_minutes],
    ];
    card.dataset.index = String(index);
    for (const [name, labelText, type, value] of fields) {
      const label = document.createElement("label");
      label.className = "draft-edit-field";
      label.textContent = labelText;
      const input = document.createElement("input");
      input.type = type;
      input.dataset.sessionField = name;
      input.value = String(value ?? "");
      if (type === "number") { input.min = "1"; input.max = String(plan.minutes_per_day); input.required = true; }
      if (type === "date") { input.min = plan.start_date; input.max = plan.deadline; input.required = true; }
      if (name === "title") { input.maxLength = 200; input.required = true; }
      if (name === "description") input.maxLength = 2000;
      label.append(input);
      card.append(label);
    }
    const remove = document.createElement("button");
    remove.className = "secondary-button draft-remove";
    remove.type = "button";
    remove.dataset.removeSession = String(index);
    remove.textContent = "Remove session";
    card.append(remove);
    sessionContainer.append(card);
  });

  document.querySelector("#draft-totals").textContent =
    `Total planned study time: ${plan.total_minutes} minutes`;
  draftPanel.hidden = false;
  draftPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function syncDraftFromEditor() {
  if (!currentDraft) return;
  const updated = [];
  for (const card of sessionContainer.querySelectorAll(".draft-session")) {
    const get = (field) => card.querySelector(`[data-session-field="${field}"]`).value;
    updated.push({
      date: get("date"), title: get("title").trim(), description: get("description").trim(),
      estimated_minutes: Number(get("estimated_minutes")),
    });
  }
  currentDraft.sessions = updated;
  currentDraft.total_minutes = updated.reduce((total, item) => total + item.estimated_minutes, 0);
  document.querySelector("#draft-totals").textContent = `Total planned study time: ${currentDraft.total_minutes} minutes`;
}

sessionContainer.addEventListener("input", syncDraftFromEditor);
sessionContainer.addEventListener("click", (event) => {
  const remove = event.target.closest("[data-remove-session]");
  if (!remove || !currentDraft) return;
  syncDraftFromEditor();
  currentDraft.sessions.splice(Number(remove.dataset.removeSession), 1);
  currentDraft.total_minutes = currentDraft.sessions.reduce((total, item) => total + item.estimated_minutes, 0);
  renderDraft(currentDraft);
});

document.querySelector("#add-plan-session").addEventListener("click", () => {
  if (!currentDraft) return;
  syncDraftFromEditor();
  currentDraft.sessions.push({ date: currentDraft.start_date, title: "Study session", description: "", estimated_minutes: Math.min(30, currentDraft.minutes_per_day) });
  currentDraft.total_minutes += Math.min(30, currentDraft.minutes_per_day);
  renderDraft(currentDraft);
});

plannerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showNotice("");
  const button = plannerForm.querySelector("button[type=submit]");
  const label = button.querySelector(".button-label");
  button.disabled = true;
  label.textContent = "Building a balanced plan…";

  const values = Object.fromEntries(new FormData(plannerForm));
  values.study_days_per_week = Number(values.study_days_per_week);
  values.minutes_per_day = Number(values.minutes_per_day);
  try {
    const response = await window.studyPilotFetch("/api/plans/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    renderDraft(result);
  } catch (error) {
    showNotice(`Couldn't generate a plan: ${error.message}`);
  } finally {
    button.disabled = false;
    label.textContent = "Generate a draft plan";
  }
});

document.querySelector("#discard-draft").addEventListener("click", () => {
  currentDraft = null;
  draftPanel.hidden = true;
  showNotice("Draft discarded. No tasks were created.");
});

document.querySelector("#approve-draft").addEventListener("click", async (event) => {
  if (!currentDraft) return;
  syncDraftFromEditor();
  showNotice("");
  const button = event.currentTarget;
  const label = button.querySelector(".button-label");
  button.disabled = true;
  label.textContent = "Adding approved sessions…";
  try {
    const response = await window.studyPilotFetch("/api/plans/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentDraft),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    currentDraft = null;
    draftPanel.hidden = true;
    showNotice(`Approved: ${result.created_count} study session task(s) added. View them on the dashboard.`);
  } catch (error) {
    showNotice(`Couldn't add the approved plan: ${error.message}`);
  } finally {
    button.disabled = false;
    label.textContent = "Approve and add tasks";
  }
});

checkProvider();
