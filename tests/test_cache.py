from trajectory_gym.llm.cache import ResponseCache, cache_key
from trajectory_gym.llm.providers import LLMResponse


def test_cache_key_deterministic_and_sensitive_to_inputs():
    msgs = [{"role": "user", "content": "hello"}]
    k1 = cache_key("mock", "m1", 0.3, msgs)
    k2 = cache_key("mock", "m1", 0.3, msgs)
    k3 = cache_key("mock", "m1", 0.7, msgs)
    k4 = cache_key("mock", "m2", 0.3, msgs)
    assert k1 == k2
    assert k1 != k3
    assert k1 != k4


def test_cache_put_and_get_roundtrip(tmp_path):
    cache = ResponseCache(tmp_path / "cache.sqlite3")
    key = cache_key("mock", "m1", 0.3, [{"role": "user", "content": "hi"}])
    assert cache.get(key) is None

    response = LLMResponse(text="hello world", input_tokens=2, output_tokens=2)
    cache.put(key, response)

    cached = cache.get(key)
    assert cached is not None
    assert cached.text == "hello world"
    assert cached.input_tokens == 2
    assert cached.output_tokens == 2
    cache.close()


def test_cache_persists_across_instances(tmp_path):
    path = tmp_path / "cache.sqlite3"
    key = cache_key("mock", "m1", 0.3, [{"role": "user", "content": "persist"}])

    cache_1 = ResponseCache(path)
    cache_1.put(key, LLMResponse(text="persisted", input_tokens=1, output_tokens=1))
    cache_1.close()

    cache_2 = ResponseCache(path)
    cached = cache_2.get(key)
    assert cached is not None
    assert cached.text == "persisted"
    cache_2.close()
