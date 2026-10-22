"""StudyPilot web application entry point."""

import os

import uvicorn


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.api.routes:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
