import json
from urllib.request import Request

from app.ai import llm_client


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return json.dumps(
            {"choices": [{"message": {"content": '{"answer":"A semiconductor controls conduction."}'}}]}
        ).encode("utf-8")


def test_openai_compatible_chat_uses_json_mode_and_bearer_key(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(llm_client, "LLM_API_KEY", "test-secret")
    monkeypatch.setattr(llm_client, "LLM_MODEL", "gpt-4o-mini")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(llm_client, "urlopen", fake_urlopen)

    answer = llm_client.complete_chat("Tutor", "Explain a semiconductor.", json_mode=True)

    request = captured["request"]
    assert isinstance(request, Request)
    assert request.full_url == "https://api.openai.com/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-secret"
    assert json.loads(request.data)["response_format"] == {"type": "json_object"}
    assert json.loads(request.data)["model"] == "gpt-4o-mini"
    assert captured["timeout"] == 120
    assert answer == '{"answer":"A semiconductor controls conduction."}'


def test_chat_rejects_oversized_prompt_before_request(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(llm_client, "LLM_API_KEY", "test-secret")
    monkeypatch.setattr(llm_client, "LLM_MODEL", "test-model")
    monkeypatch.setattr(
        llm_client,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network call")),
    )

    try:
        llm_client.complete_chat("system", "x" * (llm_client.MAX_USER_PROMPT_CHARS + 1))
    except RuntimeError as error:
        assert "too large" in str(error)
    else:
        raise AssertionError("oversized prompt was accepted")


def test_chat_rejects_provider_url_with_embedded_credentials(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_BASE_URL", "https://user:pass@example.com/v1")
    monkeypatch.setattr(llm_client, "LLM_API_KEY", "test-secret")
    monkeypatch.setattr(llm_client, "LLM_MODEL", "test-model")

    try:
        llm_client.complete_chat("Tutor", "Explain a semiconductor.")
    except RuntimeError as error:
        assert "without credentials" in str(error)
        assert "pass" not in str(error)
    else:
        raise AssertionError("provider URL with credentials was accepted")


def test_chat_limits_provider_response_size(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(llm_client, "LLM_API_KEY", "test-secret")
    monkeypatch.setattr(llm_client, "LLM_MODEL", "test-model")

    class LargeResponse(FakeResponse):
        def read(self, size=-1):
            return b" " * (llm_client.MAX_RESPONSE_BYTES + 1)

    monkeypatch.setattr(llm_client, "urlopen", lambda *_args, **_kwargs: LargeResponse())
    try:
        llm_client.complete_chat("Tutor", "Explain a semiconductor.")
    except RuntimeError as error:
        assert "2 MB limit" in str(error)
    else:
        raise AssertionError("oversized provider response was accepted")
