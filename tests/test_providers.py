"""Offline tests for provider response parsing (no network — requests.post
is monkeypatched)."""
from trajectory_gym.llm import providers


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.headers = {}
        self.text = str(json_data)

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


def test_openrouter_handles_null_content_without_crashing(monkeypatch):
    """Regression test: a response can have `content: null` (e.g. a
    reasoning model whose entire budget went to reasoning, leaving nothing
    in the visible answer). This must come back as an empty string, not
    crash — client.py already knows how to treat an empty response as
    "don't cache, let the caller retry"."""
    monkeypatch.setattr(
        providers,
        "_post_with_retries",
        lambda url, **kw: _FakeResponse(
            {"choices": [{"message": {"content": None}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        ),
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    provider = providers.OpenRouterProvider()
    response = provider.complete([{"role": "user", "content": "hi"}], model="m", temperature=0.3, max_tokens=100)
    assert response.text == ""


def test_openai_compatible_handles_null_content_without_crashing(monkeypatch):
    monkeypatch.setattr(
        providers,
        "_post_with_retries",
        lambda url, **kw: _FakeResponse(
            {"choices": [{"message": {"content": None}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        ),
    )
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://example.com/v1")
    provider = providers.OpenAICompatibleProvider()
    response = provider.complete([{"role": "user", "content": "hi"}], model="m", temperature=0.3, max_tokens=100)
    assert response.text == ""
