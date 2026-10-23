const form = document.querySelector("#doubt-form");
const providerNotice = document.querySelector("#provider-notice");
const errorNotice = document.querySelector("#doubt-error");
const resultPanel = document.querySelector("#doubt-result");
const guidePanel = document.querySelector(".doubt-guide-panel");
const questionField = form.elements.question;
const documentField = document.querySelector("#document-file");

function setList(selector, values) {
  const list = document.querySelector(selector);
  list.replaceChildren();
  for (const value of values) {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  }
}

async function checkAIStatus() {
  try {
    const response = await window.studyPilotFetch("/api/ai/status");
    if (!response.ok) throw new Error(`Status check failed (${response.status})`);
    const status = await response.json();
    if (!status.configured) {
      providerNotice.hidden = false;
      providerNotice.textContent =
        "AI is not connected yet. Configure LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL privately on the server or in Vercel settings, then restart or redeploy. Do not paste an API key into this page.";
    }
  } catch (error) {
    providerNotice.hidden = false;
    providerNotice.textContent = `Could not check AI setup: ${error.message}`;
  }
}

function showResult(result) {
  document.querySelector("#difficulty-badge").textContent = result.difficulty;
  document.querySelector("#difficulty-badge").className = `difficulty-badge ${result.difficulty}`;
  document.querySelector("#answer-text").textContent = result.answer;
  document.querySelector("#analysis-text").textContent = result.analysis;
  setList("#steps-list", result.steps);
  setList("#concepts-list", result.concepts);

  const documentSource = document.querySelector("#document-source");
  const analyzedDocument = result.document;
  documentSource.hidden = !analyzedDocument;
  if (analyzedDocument) {
    const parts = [analyzedDocument.filename, analyzedDocument.kind, (analyzedDocument.sources || []).join(", ")];
    if (analyzedDocument.truncated) parts.push("excerpt shortened to fit analysis limits");
    document.querySelector("#document-source-text").textContent = parts.filter(Boolean).join(" · ");
  }

  const misconceptionWrap = document.querySelector("#misconception-wrap");
  misconceptionWrap.hidden = !result.misconception;
  document.querySelector("#misconception-text").textContent = result.misconception;

  const followupWrap = document.querySelector("#followup-wrap");
  followupWrap.hidden = !result.follow_up;
  document.querySelector("#followup-text").textContent = result.follow_up;
  guidePanel.hidden = true;
  resultPanel.hidden = false;
}

function updateQuestionRequirement() {
  const hasDocument = documentField.files.length > 0;
  questionField.required = !hasDocument;
  document.querySelector("#question-label").innerHTML = hasDocument
    ? 'Your question <em>optional with a document</em>'
    : 'Your doubt <em>required</em>';
}

documentField.addEventListener("change", updateQuestionRequirement);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorNotice.hidden = true;
  guidePanel.hidden = false;
  resultPanel.hidden = true;
  const button = form.querySelector("button[type=submit]");
  const buttonLabel = button.querySelector(".button-label");
  button.disabled = true;
  buttonLabel.textContent = "Working through your question…";

  const file = documentField.files[0];
  if (file && file.size > 10 * 1024 * 1024) {
    errorNotice.textContent = "Files must be 10 MB or smaller.";
    errorNotice.hidden = false;
    button.disabled = false;
    buttonLabel.textContent = "Explain and analyze";
    return;
  }
  const formData = new FormData(form);
  const values = Object.fromEntries(formData);
  delete values.document;
  try {
    const response = file
      ? await window.studyPilotFetch("/api/doubts/analyze-document", {
          method: "POST",
          body: formData,
        })
      : await window.studyPilotFetch("/api/doubts/solve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(values),
        });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    showResult(result);
  } catch (error) {
    errorNotice.textContent = `Couldn't analyze this doubt: ${error.message}`;
    errorNotice.hidden = false;
  } finally {
    button.disabled = false;
    buttonLabel.textContent = file ? "Analyze document and explain" : "Explain and analyze";
  }
});

updateQuestionRequirement();

checkAIStatus();
