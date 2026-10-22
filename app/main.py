"""StudyPilot web application entry point."""

import os

import uvicorn


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    # Cloud hosts route traffic to the container's network interface, so bind
    # on all interfaces instead of loopback.
    uvicorn.run("app.api.routes:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
