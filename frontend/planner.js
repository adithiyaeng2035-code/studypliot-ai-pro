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

  for (const session of plan.sessions) {
    const card = document.createElement("article");
    card.className = "draft-session";
    const date = document.createElement("span");
    date.className = "draft-session-date";
    date.textContent = new Intl.DateTimeFormat(undefined, {
      weekday: "short", month: "short", day: "numeric", year: "numeric",
    }).format(new Date(`${session.date}T12:00:00`));
    const title = document.createElement("h3");
    title.textContent = session.title;
    const description = document.createElement("p");
    description.textContent = session.description;
    const minutes = document.createElement("span");
    minutes.className = "draft-session-time";
    minutes.textContent = `${session.estimated_minutes} minutes`;
    card.append(date, title, description, minutes);
    sessionContainer.append(card);
  }

  document.querySelector("#draft-totals").textContent =
    `Total planned study time: ${plan.total_minutes} minutes`;
  draftPanel.hidden = false;
  draftPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

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
