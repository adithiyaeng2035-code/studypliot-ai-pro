const status = document.querySelector("#auth-status");

async function submitAuth(path, values) {
  status.textContent = "Working…";
  try {
    const response = await fetch(`/api/auth/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(values),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
    window.location.assign("/");
  } catch (error) {
    status.textContent = error.message;
  }
}

document.querySelector("#login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  submitAuth("login", values);
});

document.querySelector("#register-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  submitAuth("register", values);
});

fetch("/api/auth/me", { cache: "no-store" })
  .then((response) => response.json())
  .then((state) => {
    if (!state.auth_enabled) {
      status.textContent = "Account access is disabled. Set AUTH_ENABLED=true to enable hosted accounts.";
    } else if (state.authenticated) {
      window.location.replace("/");
    }
  })
  .catch(() => {
    status.textContent = "Could not reach StudyPilot. Check the server and try again.";
  });
