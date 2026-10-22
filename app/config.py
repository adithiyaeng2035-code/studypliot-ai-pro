"""Environment-based application settings."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("STUDYPILOT_DATA_DIR", PROJECT_ROOT / "data"))
DATABASE_PATH = Path(os.getenv("STUDYPILOT_DATABASE", DATA_DIR / "studypilot.sqlite3"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_BACKEND = os.getenv("DATABASE_BACKEND", "").lower()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
AUTH_ALLOW_REGISTRATION = os.getenv("AUTH_ALLOW_REGISTRATION", "true").strip().lower() in {
    "1", "true", "yes"
}
AUTH_COOKIE_SECURE = os.getenv(
    "AUTH_COOKIE_SECURE", "true" if AUTH_ENABLED else "false"
).strip().lower() in {
    "1", "true", "yes"
}
