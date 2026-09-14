"""LLM providers behind one interface. Model IDs and endpoints are never
hardcoded here — they come from config/models.yaml via config.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import requests
from pydantic import BaseModel

Message = dict[str, str]  # {"role": ..., "content": ...}

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think_tags(text: str) -> str:
    """Some models (e.g. Qwen3's "thinking" mode) emit chain-of-thought
    inline as <think>...</think> before the real answer, rather than in a
    separate field (contrast gpt-oss's `reasoning` field). The thinking
    text often contains example/quoted JSON that would otherwise confuse a
    naive "grab the first {...last}" extraction."""
    return _THINK_BLOCK.sub("", text).strip()

_MAX_RETRIES = 5
_RETRY_BACKOFF_SECONDS = 3
_RATE_LIMIT_DEFAULT_WAIT_SECONDS = 15
_RATE_LIMIT_MAX_WAIT_SECONDS = 30
"""Some providers report a Retry-After meant for a coarse daily/hourly quota
reset (seen: ~2.5 hours from Groq's per-window request quota) rather than
the fast per-minute token quota that's actually relevant here. Blindly
sleeping that long would hang a batch run for hours with no visible
progress. Cap it and fail fast instead — the response cache makes resuming
a batch run cheap, so failing fast and re-running beats hanging silently."""


def _post_with_retries(url: str, **kwargs) -> requests.Response:
    """A long batch run (Phase 4+) makes hundreds of calls — a single
    transient network blip or rate-limit response shouldn't kill the whole
    run and force re-running everything already paid for (the cache makes
    re-running cheap, but not free of wall-clock time)."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(url, **kwargs)
            if resp.status_code == 429:
                requested_wait = float(resp.headers.get("Retry-After", _RATE_LIMIT_DEFAULT_WAIT_SECONDS))
                wait = min(requested_wait, _RATE_LIMIT_MAX_WAIT_SECONDS)
                time.sleep(wait)
                last_error = requests.exceptions.HTTPError(f"429 rate limited: {resp.text[:200]}", response=resp)
                continue
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise last_error


class LLMResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int


class Provider(ABC):
    @abstractmethod
    def complete(
        self, messages: list[Message], model: str, temperature: float, max_tokens: int
    ) -> LLMResponse: ...


def _approx_tokens(text: str) -> int:
    # Word-count heuristic, not a real tokenizer — good enough for cost
    # estimates and budget ceilings; swap for tiktoken if it matters.
    return max(1, len(text.split()))


class MockProvider(Provider):
    """Deterministic, zero-cost, zero-network. Used by the whole test suite
    and by `make demo` when no live provider is configured.

    Output is a hash of the input messages, so identical calls are byte-
    identical (required for cache/determinism tests) and different calls
    produce different output (so it's not just a hardcoded constant).
    """

    def complete(
        self, messages: list[Message], model: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        payload = json.dumps(messages, sort_keys=True) + f"|{model}|{temperature}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        text = f"[mock:{model}:{digest[:12]}]"
        input_tokens = sum(_approx_tokens(m["content"]) for m in messages)
        return LLMResponse(
            text=text, input_tokens=input_tokens, output_tokens=_approx_tokens(text)
        )


class OpenRouterProvider(Provider):
    def complete(
        self, messages: list[Message], model: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set — required for --live runs")
        resp = _post_with_retries(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            input_tokens=usage.get("prompt_tokens", _approx_tokens(text)),
            output_tokens=usage.get("completion_tokens", _approx_tokens(text)),
        )


class GeminiProvider(Provider):
    def complete(
        self, messages: list[Message], model: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set — required for --live runs")
        contents = [
            {"role": "user" if m["role"] != "assistant" else "model", "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        resp = _post_with_retries(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json={
                "contents": contents,
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
            timeout=60,
        )
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            input_tokens=usage.get("promptTokenCount", _approx_tokens(text)),
            output_tokens=usage.get("candidatesTokenCount", _approx_tokens(text)),
        )


class OpenAICompatibleProvider(Provider):
    def complete(
        self, messages: list[Message], model: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
        base_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL")
        if not api_key or not base_url:
            raise RuntimeError(
                "OPENAI_COMPATIBLE_API_KEY / OPENAI_COMPATIBLE_BASE_URL not set — required for --live runs"
            )
        resp = _post_with_retries(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            input_tokens=usage.get("prompt_tokens", _approx_tokens(text)),
            output_tokens=usage.get("completion_tokens", _approx_tokens(text)),
        )


_PROVIDERS: dict[str, type[Provider]] = {
    "mock": MockProvider,
    "openrouter": OpenRouterProvider,
    "gemini": GeminiProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


def get_provider(name: str) -> Provider:
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise ValueError(f"unknown provider {name!r}; known: {sorted(_PROVIDERS)}") from None
