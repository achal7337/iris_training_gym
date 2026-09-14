"""SQLite response cache keyed on sha256(provider + model + temperature +
messages_json). Checked before every LLM call (Section 2/15 of prompt.md) —
this is what makes iteration free and `make demo` network-independent.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .providers import LLMResponse, Message

DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[3] / "data" / "llm_cache.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def cache_key(provider: str, model: str, temperature: float, messages: list[Message]) -> str:
    messages_json = json.dumps(messages, sort_keys=True)
    payload = f"{provider}|{model}|{temperature}|{messages_json}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, path: Path | str = DEFAULT_CACHE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def get(self, key: str) -> LLMResponse | None:
        row = self._conn.execute(
            "SELECT text, input_tokens, output_tokens FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        text, input_tokens, output_tokens = row
        return LLMResponse(text=text, input_tokens=input_tokens, output_tokens=output_tokens)

    def put(self, key: str, response: LLMResponse) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, text, input_tokens, output_tokens) VALUES (?, ?, ?, ?)",
            (key, response.text, response.input_tokens, response.output_tokens),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
