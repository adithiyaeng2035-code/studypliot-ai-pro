"""Small OpenAI-compatible chat completions client using the Python standard library."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

REQUEST_TIMEOUT_SECONDS = 30
MAX_SYSTEM_PROMPT_CHARS = 30_000
MAX_USER_PROMPT_CHARS = 50_000
MAX_RESPONSE_BYTES = 2_000_000
MAX_COMPLETION_TOKENS = 4096


class AIProviderNotConfigured(RuntimeError):
    """Raised when a feature requiring an external LLM has no provider settings."""


def is_configured() -> bool:
    return bool(LLM_BASE_URL and LLM_API_KEY and LLM_MODEL)


def complete_chat(system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> str:
    if not is_configured():
        raise AIProviderNotConfigured(
            "Configure LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL to enable StudyPilot AI features."
        )
    if not isinstance(system_prompt, str) or not isinstance(user_prompt, str):
        raise TypeError("AI prompt must be text.")
    if len(system_prompt) > MAX_SYSTEM_PROMPT_CHARS or len(user_prompt) > MAX_USER_PROMPT_CHARS:
        raise RuntimeError("AI prompt is too large. Shorten the request and try again.")
    base_url = LLM_BASE_URL.rstrip("/")
    parsed_url = urlsplit(base_url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise RuntimeError("AI provider URL must be an HTTP(S) base URL without credentials or query parameters.")
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
        "max_tokens": MAX_COMPLETION_TOKENS,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_bytes = response.read(MAX_RESPONSE_BYTES + 1)
        if len(response_bytes) > MAX_RESPONSE_BYTES:
            raise RuntimeError("AI provider response exceeded the 2 MB limit.")
        payload = json.loads(response_bytes.decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(
            f"AI provider request failed with HTTP status {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError("AI provider could not be reached or timed out.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("AI provider returned an invalid JSON response.") from error
    except ValueError as error:
        raise RuntimeError(f"AI provider URL or response is invalid: {error}") from error
    try:
        answer = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("AI provider response did not contain a chat completion.") from error
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("AI provider returned an empty response.")
    return answer.strip()
