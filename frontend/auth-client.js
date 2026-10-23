const authPage = window.location.pathname === "/login.html";
window.studyPilotCsrfToken = "";

if (!authPage) {
  window.studyPilotAuthReady = (async () => {
    try {
      const response = await fetch("/api/auth/me", { cache: "no-store" });
      if (!response.ok) throw new Error(`Account check failed (${response.status})`);
      const state = await response.json();
      if (state.auth_enabled && !state.authenticated) {
        window.location.replace("/login.html");
        return false;
      }
      if (state.authenticated) {
        window.studyPilotCsrfToken = state.csrf_token;
        const accountBox = document.querySelector(".account-box");
        if (accountBox) accountBox.hidden = false;
        const email = document.querySelector("#account-email");
        if (email) {
          const displayName = state.user.full_name || state.user.email;
          email.textContent = displayName;
          email.title = state.user.email;
          email.setAttribute("aria-label", `Signed in as ${displayName}`);
        }
        document.querySelectorAll(".account-privacy").forEach((item) => item.hidden = false);
      }
      return true;
    } catch (error) {
      const message = document.querySelector("#notice, #planner-notice, #doubt-error, #tutor-notice");
      if (message) {
        message.textContent = `Couldn't verify your account session: ${error.message}`;
        message.hidden = false;
      }
      return false;
    }
  })();

  window.studyPilotFetch = async (url, options = {}) => {
    if (!(await window.studyPilotAuthReady)) throw new Error("Account session is not ready.");
    const headers = new Headers(options.headers || {});
    const method = (options.method || "GET").toUpperCase();
    if (!["GET", "HEAD", "OPTIONS"].includes(method) && window.studyPilotCsrfToken) {
      headers.set("X-CSRF-Token", window.studyPilotCsrfToken);
    }
    return fetch(url, { ...options, headers, credentials: "same-origin" });
  };

  document.querySelector("#sign-out")?.addEventListener("click", async () => {
    try {
      await window.studyPilotFetch("/api/auth/logout", { method: "POST" });
    } finally {
      window.location.assign("/login.html");
    }
  });

  document.querySelectorAll("#delete-account").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm("Permanently delete your account, tasks, and study-session history? This cannot be undone.")) return;
      const password = window.prompt("Enter your password to confirm account deletion:");
      if (password === null) return;
      try {
        const response = await window.studyPilotFetch("/api/auth/account", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password }),
        });
        if (!response.ok) {
          const payload = await response.json();
          throw new Error(payload.detail || `Request failed (${response.status})`);
        }
        window.location.assign("/login.html");
      } catch (error) {
        window.alert(`Account deletion failed: ${error.message}`);
      }
    });
  });
}
