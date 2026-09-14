"""The one LLM entry point: complete(messages, role, **kw).

role in {agent, judge, selector, writer}; config/models.yaml maps each role
to a provider/model/temperature/max_tokens. Every call checks the response
cache first (Section 2 of prompt.md).
"""
from __future__ import annotations

import os
from functools import lru_cache

from ..config import get_models_config
from .cache import ResponseCache, cache_key
from .providers import LLMResponse, Message, get_provider

MOCK_MODE_ENV_VAR = "TRAJECTORY_GYM_MOCK"
"""Set to "1" to force every role onto the mock provider regardless of
config/models.yaml — this is what keeps `make test` at $0 even once real
providers are configured for live runs. Set by tests/conftest.py."""


@lru_cache
def _cache() -> ResponseCache:
    return ResponseCache()


def complete(
    messages: list[Message],
    role: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    role_config = get_models_config().for_role(role)
    provider_name = "mock" if os.environ.get(MOCK_MODE_ENV_VAR) == "1" else role_config.provider
    model = role_config.model
    temp = role_config.temperature if temperature is None else temperature
    tokens = role_config.max_tokens if max_tokens is None else max_tokens

    key = cache_key(provider_name, model, temp, messages)
    cache = _cache()
    cached = cache.get(key)
    if cached is not None:
        return cached

    provider = get_provider(provider_name)
    response = provider.complete(messages, model=model, temperature=temp, max_tokens=tokens)
    was_truncated = response.output_tokens >= tokens
    if response.text.strip() and not was_truncated:
        # Never cache an empty response (a reasoning model can exhaust
        # max_tokens on hidden/inline reasoning before emitting content) or
        # one that hit the token ceiling (almost certainly cut off mid-
        # answer). Either would permanently poison this exact prompt — the
        # next call for it would keep replaying the same broken response
        # forever, even after raising max_tokens in config.
        cache.put(key, response)
    return response
