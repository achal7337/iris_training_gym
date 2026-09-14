import trajectory_gym.llm.client as client
from trajectory_gym.config import get_models_config
from trajectory_gym.llm.cache import ResponseCache
from trajectory_gym.llm.providers import LLMResponse, Provider


def test_complete_uses_mock_provider_by_default_and_is_deterministic(tmp_path, monkeypatch):
    test_cache = ResponseCache(tmp_path / "cache.sqlite3")
    monkeypatch.setattr(client, "_cache", lambda: test_cache)

    messages = [{"role": "user", "content": "ticket: my order never arrived"}]
    r1 = client.complete(messages, role="agent")
    r2 = client.complete(messages, role="agent")

    assert r1.text == r2.text
    assert r1.text.startswith("[mock:")


def test_complete_hits_cache_on_second_call(tmp_path, monkeypatch):
    test_cache = ResponseCache(tmp_path / "cache.sqlite3")
    monkeypatch.setattr(client, "_cache", lambda: test_cache)

    messages = [{"role": "user", "content": "same input twice"}]
    client.complete(messages, role="judge")
    row_count_after_first = test_cache._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]

    client.complete(messages, role="judge")
    row_count_after_second = test_cache._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]

    assert row_count_after_first == 1
    assert row_count_after_second == 1  # no new row — second call was a cache hit


def test_different_roles_can_produce_different_output(tmp_path, monkeypatch):
    test_cache = ResponseCache(tmp_path / "cache.sqlite3")
    monkeypatch.setattr(client, "_cache", lambda: test_cache)

    messages = [{"role": "user", "content": "shared prompt text"}]
    agent_resp = client.complete(messages, role="agent")
    judge_resp = client.complete(messages, role="judge")

    # different role -> different (provider, model, temperature) -> different cache key
    assert agent_resp.text != judge_resp.text


def test_mock_mode_env_var_overrides_a_live_provider_in_config(tmp_path, monkeypatch):
    """Regression test for the cost-safety switch: even if config/models.yaml
    points a role at a real provider, TRAJECTORY_GYM_MOCK=1 (set for the
    whole test session in conftest.py) must force the mock provider so
    `make test` never touches the network."""
    role_config = get_models_config().for_role("agent")
    assert role_config.provider != "mock", (
        "this test is only meaningful once the agent role points at a live "
        "provider in config/models.yaml — if it's back to mock, that's fine, "
        "just confirm the override still works via the other tests"
    )

    test_cache = ResponseCache(tmp_path / "cache.sqlite3")
    monkeypatch.setattr(client, "_cache", lambda: test_cache)

    response = client.complete([{"role": "user", "content": "should never hit the network"}], role="agent")
    assert response.text.startswith("[mock:")


def test_empty_responses_are_never_cached(tmp_path, monkeypatch):
    """Regression test: a reasoning model that exhausts max_tokens on hidden
    reasoning can return empty content. Caching that would permanently
    poison the exact prompt (config bumping max_tokens later wouldn't help,
    since max_tokens isn't part of the cache key by design)."""

    class EmptyThenRealProvider(Provider):
        def __init__(self):
            self.calls = 0

        def complete(self, messages, model, temperature, max_tokens):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(text="", input_tokens=5, output_tokens=0)
            return LLMResponse(text="real answer", input_tokens=5, output_tokens=2)

    test_cache = ResponseCache(tmp_path / "cache.sqlite3")
    monkeypatch.setattr(client, "_cache", lambda: test_cache)
    fake_provider = EmptyThenRealProvider()
    monkeypatch.setattr(client, "get_provider", lambda name: fake_provider)

    messages = [{"role": "user", "content": "some judge prompt"}]
    r1 = client.complete(messages, role="judge")
    assert r1.text == ""

    r2 = client.complete(messages, role="judge")
    assert r2.text == "real answer"
    assert fake_provider.calls == 2  # empty response was not cached, so the second call hit the provider again


def test_truncated_responses_are_never_cached(tmp_path, monkeypatch):
    """Regression test: a "thinking" model (e.g. Qwen3) can spend its whole
    max_tokens budget on inline <think> reasoning and get cut off before
    ever reaching the answer. Caching that would permanently poison the
    prompt even after raising max_tokens, since max_tokens isn't part of
    the cache key."""
    role_config = get_models_config().for_role("agent")

    class TruncatedThenRealProvider(Provider):
        def __init__(self):
            self.calls = 0

        def complete(self, messages, model, temperature, max_tokens):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(text="<think>still thinking...", input_tokens=5, output_tokens=max_tokens)
            return LLMResponse(text='{"ok": true}', input_tokens=5, output_tokens=10)

    test_cache = ResponseCache(tmp_path / "cache.sqlite3")
    monkeypatch.setattr(client, "_cache", lambda: test_cache)
    fake_provider = TruncatedThenRealProvider()
    monkeypatch.setattr(client, "get_provider", lambda name: fake_provider)

    messages = [{"role": "user", "content": "some agent prompt"}]
    r1 = client.complete(messages, role="agent")
    assert r1.output_tokens == role_config.max_tokens  # hit the ceiling exactly -> truncated

    r2 = client.complete(messages, role="agent")
    assert r2.text == '{"ok": true}'
    assert fake_provider.calls == 2  # truncated response was not cached
