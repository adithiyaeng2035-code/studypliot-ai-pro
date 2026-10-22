const tutorForm = document.querySelector("#tutor-form");
const messageInput = document.querySelector("#tutor-message");
const chatMessages = document.querySelector("#chat-messages");
const tutorNotice = document.querySelector("#tutor-notice");
const voiceButton = document.querySelector("#voice-input");
const voiceStatus = document.querySelector("#voice-status");
const modeSelect = document.querySelector("#help-mode");
const studyContextInput = document.querySelector("#study-context");
const voiceLanguage = document.querySelector("#voice-language");
const quickPrompts = document.querySelector("#quick-prompts");
const chatHistory = [];

function addMessage(role, text, { speakable = false } = {}) {
  const article = document.createElement("article");
  article.className = `chat-message ${role === "user" ? "user-message" : "assistant-message"}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "Y" : "S";
  const content = document.createElement("div");
  content.className = "message-content";
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "StudyPilot assistant";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  content.append(label, paragraph);
  if (role === "assistant" && speakable && "speechSynthesis" in window) {
    const tools = document.createElement("div");
    tools.className = "message-tools";
    const speak = document.createElement("button");
    speak.type = "button";
    speak.textContent = "🔊 Read aloud";
    speak.addEventListener("click", () => {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
    });
    tools.append(speak);
    content.append(tools);
  }
  article.append(avatar, content);
  chatMessages.append(article);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return paragraph;
}

tutorForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  tutorNotice.hidden = true;
  addMessage("user", message);
  messageInput.value = "";
  const pending = addMessage("assistant", "Thinking through your question…");
  const submit = document.querySelector("#send-question");
  submit.disabled = true;
  try {
    const response = await window.studyPilotFetch("/api/tutor/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history: chatHistory.slice(-8),
        mode: modeSelect.value,
        study_context: studyContextInput.value.trim(),
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    pending.textContent = result.reply;
    if (!result.ai_enabled) {
      tutorNotice.textContent = "AI is not connected yet. Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL to enable tutor responses.";
      tutorNotice.hidden = false;
    }
    const assistant = pending.closest(".chat-message");
    if ("speechSynthesis" in window) {
      const tools = document.createElement("div");
      tools.className = "message-tools";
      const speak = document.createElement("button");
      speak.type = "button";
      speak.textContent = "🔊 Read aloud";
      speak.addEventListener("click", () => {
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(result.reply));
      });
      tools.append(speak);
      assistant.querySelector(".message-content").append(tools);
    }
    chatHistory.push({ role: "user", content: message }, { role: "assistant", content: result.reply });
    quickPrompts.hidden = true;
  } catch (error) {
    pending.textContent = `I couldn't reach the tutor: ${error.message}`;
  } finally {
    submit.disabled = false;
    messageInput.focus();
  }
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    tutorForm.requestSubmit();
  }
});

document.querySelector("#clear-chat").addEventListener("click", () => {
  chatHistory.length = 0;
  chatMessages.replaceChildren();
  addMessage("assistant", "New conversation started. What can I help you with?");
  quickPrompts.hidden = false;
  chatMessages.append(quickPrompts);
  tutorNotice.hidden = true;
  window.speechSynthesis?.cancel();
});

quickPrompts.addEventListener("click", (event) => {
  const button = event.target.closest("[data-prompt]");
  if (!button) return;
  messageInput.value = button.dataset.prompt;
  if (button.dataset.mode) modeSelect.value = button.dataset.mode;
  messageInput.focus();
  messageInput.setSelectionRange(messageInput.value.length, messageInput.value.length);
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SpeechRecognition) {
  voiceButton.disabled = true;
  voiceButton.title = "Voice input is not supported in this browser.";
  voiceStatus.textContent = "Voice input is not supported in this browser.";
} else {
  const recognition = new SpeechRecognition();
  const preferredVoiceLanguage = Array.from(voiceLanguage.options).find(
    (option) => option.value.toLowerCase().startsWith((navigator.language || "en-US").slice(0, 2).toLowerCase()),
  );
  if (preferredVoiceLanguage) voiceLanguage.value = preferredVoiceLanguage.value;
  recognition.lang = voiceLanguage.value;
  recognition.interimResults = true;
  recognition.continuous = false;
  voiceLanguage.addEventListener("change", () => { recognition.lang = voiceLanguage.value; });
  let finalTranscript = "";
  voiceButton.addEventListener("click", () => {
    if (voiceButton.classList.contains("listening")) {
      recognition.stop();
      return;
    }
    finalTranscript = "";
    try {
      recognition.start();
    } catch {
      voiceStatus.textContent = "Microphone is already starting. Try again in a moment.";
    }
  });
  recognition.onstart = () => {
    voiceButton.classList.add("listening");
    voiceButton.setAttribute("aria-label", "Stop voice input");
    voiceButton.querySelector("span").textContent = "Listening";
    voiceStatus.textContent = "Listening… speak your question.";
  };
  recognition.onresult = (event) => {
    let interim = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const transcript = event.results[index][0].transcript;
      if (event.results[index].isFinal) finalTranscript += `${transcript} `;
      else interim += transcript;
    }
    messageInput.value = `${finalTranscript}${interim}`.trimStart();
  };
  recognition.onerror = (event) => {
    voiceStatus.textContent = event.error === "not-allowed" ? "Allow microphone access in your browser to use voice input." : `Voice input error: ${event.error}.`;
  };
  recognition.onend = () => {
    voiceButton.classList.remove("listening");
    voiceButton.setAttribute("aria-label", "Start voice input");
    voiceButton.querySelector("span").textContent = "Speak";
    if (messageInput.value.trim()) voiceStatus.textContent = "Voice captured. Review it, then ask the tutor.";
  };
}
