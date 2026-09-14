"""Per-episode state: the live DB connection plus per-tool call counters
used to seed deterministic failure injection.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field


@dataclass
class EpisodeState:
    conn: sqlite3.Connection
    scenario_id: str
    call_counts: dict[str, int] = field(default_factory=dict)
    force_stale_status: bool = False
    """Set from Scenario.force_stale_status (class C10) to force the first
    `lookup_order` call to return a stale status rather than leaving it to
    the usual per-call injection roll."""

    def next_call_index(self, tool_name: str) -> int:
        idx = self.call_counts.get(tool_name, 0)
        self.call_counts[tool_name] = idx + 1
        return idx

    def log_audit(self, actor: str, action: str, args: dict, result: dict, blocked: bool = False) -> None:
        self.conn.execute(
            "INSERT INTO audit_log (ts, actor, action, args_json, result_json, blocked) "
            "VALUES (datetime('now'), ?, ?, ?, ?, ?)",
            (actor, action, json.dumps(args, sort_keys=True), json.dumps(result, sort_keys=True), int(blocked)),
        )
        self.conn.commit()
