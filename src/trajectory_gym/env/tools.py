"""The seven tools — Section 7 of prompt.md. Exactly seven; do not add an
eighth (Section 12, "never build").

Failure injection is seeded on (scenario_id, tool_name, call_index) so a
given scenario fails identically on every replay (NON-NEGOTIABLE 6). No tool
here computes eligibility or a refund amount — reasoning over the policy is
the task (docs/not_built.md).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..config import get_env_config
from .state import EpisodeState

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = REPO_ROOT / "data" / "policy" / "refund_policy_v3_1.md"


def _injection_roll(scenario_id: str, tool_name: str, call_index: int) -> float:
    payload = f"{scenario_id}|{tool_name}|{call_index}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


class ToolError(Exception):
    """Raised for a caller error (bad args) — distinct from an injected
    transient failure, which is returned as a normal tool result so the
    agent can see and react to it."""


def lookup_order(state: EpisodeState, order_id: str) -> dict:
    env_cfg = get_env_config()
    idx = state.next_call_index("lookup_order")
    row = state.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        result = {"error": "NOT_FOUND", "order_id": order_id}
        state.log_audit("agent", "lookup_order", {"order_id": order_id}, result)
        return result

    order = _row_to_dict(row)
    items = state.conn.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchall()
    order["items"] = [_row_to_dict(i) for i in items]

    stale_rate = env_cfg.failure_injection.lookup_order["stale_status_rate"]
    forced = state.force_stale_status and idx == 0
    if forced or _injection_roll(state.scenario_id, "lookup_order", idx) < stale_rate:
        real_status = order["status"]
        order["status"] = "processing" if real_status == "delivered" else "delivered"
        order["_stale"] = True

    state.log_audit("agent", "lookup_order", {"order_id": order_id}, order)
    return order


def lookup_customer(state: EpisodeState, email: str | None = None, customer_id: str | None = None) -> dict:
    env_cfg = get_env_config()
    idx = state.next_call_index("lookup_customer")
    args = {"email": email, "customer_id": customer_id}

    timeout_rate = env_cfg.failure_injection.lookup_customer["timeout_rate"]
    if _injection_roll(state.scenario_id, "lookup_customer", idx) < timeout_rate:
        result = {"error": "TIMEOUT"}
        state.log_audit("agent", "lookup_customer", args, result)
        return result

    if customer_id:
        row = state.conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    elif email:
        row = state.conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
    else:
        raise ToolError("lookup_customer requires email or customer_id")

    if row is None:
        result = {"error": "NOT_FOUND"}
        state.log_audit("agent", "lookup_customer", args, result)
        return result

    customer = _row_to_dict(row)
    orders = state.conn.execute(
        "SELECT id, placed_at, total_cents FROM orders WHERE customer_id = ? ORDER BY placed_at DESC",
        (customer["id"],),
    ).fetchall()
    # A real support console lists a customer's orders with enough summary
    # info (date, amount) to spot the right one without opening each — not
    # just bare IDs. Without this, a customer with an unrelated order
    # history forces several blind lookup_order calls just to find the one
    # the ticket is about, which has nothing to do with policy reasoning.
    customer["orders"] = [
        {"order_id": o["id"], "placed_at": o["placed_at"], "total_cents": o["total_cents"]} for o in orders
    ]

    state.log_audit("agent", "lookup_customer", args, customer)
    return customer


_STOPWORDS = {
    "the", "a", "an", "of", "to", "for", "and", "or", "is", "are", "on", "in",
    "within", "may", "must", "be", "this", "that", "with", "not", "does",
}


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS}


_policy_chunks: list[dict] | None = None


def _load_policy_chunks() -> list[dict]:
    global _policy_chunks
    if _policy_chunks is not None:
        return _policy_chunks
    text = POLICY_PATH.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", text)
    chunks = []
    for section in sections[1:]:
        header, _, body = section.partition("\n")
        chunks.append({"header": f"## {header.strip()}", "body": body.strip()})
    _policy_chunks = chunks
    return chunks


def read_policy(state: EpisodeState, query: str) -> dict:
    env_cfg = get_env_config()
    idx = state.next_call_index("read_policy")
    top_k = env_cfg.read_policy_top_k
    query_tokens = _tokenize(query)
    chunks = _load_policy_chunks()
    scored = [
        (len(query_tokens & _tokenize(c["header"] + " " + c["body"])), i, c)
        for i, c in enumerate(chunks)
    ]
    scored.sort(key=lambda t: (-t[0], t[1]))
    top = [c for _, _, c in scored[:top_k]]
    result = {"chunks": top}
    state.log_audit("agent", "read_policy", {"query": query}, result)
    return result


def inspect_refund_history(state: EpisodeState, order_id: str) -> dict:
    state.next_call_index("inspect_refund_history")
    rows = state.conn.execute(
        "SELECT * FROM refunds WHERE order_id = ? ORDER BY created_at", (order_id,)
    ).fetchall()
    result = {"refunds": [_row_to_dict(r) for r in rows]}
    state.log_audit("agent", "inspect_refund_history", {"order_id": order_id}, result)
    return result


def issue_refund(state: EpisodeState, order_id: str, amount_cents: int, reason: str) -> dict:
    state.next_call_index("issue_refund")
    args = {"order_id": order_id, "amount_cents": amount_cents, "reason": reason}

    order_row = state.conn.execute("SELECT total_cents FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order_row is None:
        result = {"error": "NOT_FOUND", "order_id": order_id}
        state.log_audit("agent", "issue_refund", args, result)
        return result

    if amount_cents > order_row["total_cents"]:
        result = {"error": "AMOUNT_EXCEEDS_ORDER_TOTAL", "order_total_cents": order_row["total_cents"]}
        state.log_audit("agent", "issue_refund", args, result)
        return result

    (existing_count,) = state.conn.execute("SELECT COUNT(*) FROM refunds").fetchone()
    refund_id = f"R{existing_count + 1:06d}"
    state.conn.execute(
        "INSERT INTO refunds (id, order_id, amount_cents, reason, created_at, created_by, approved_by) "
        "VALUES (?, ?, ?, ?, datetime('now'), 'agent', NULL)",
        (refund_id, order_id, amount_cents, reason),
    )
    state.conn.commit()
    result = {"refund_id": refund_id, "order_id": order_id, "amount_cents": amount_cents}
    state.log_audit("agent", "issue_refund", args, result)
    return result


def escalate(state: EpisodeState, reason: str) -> dict:
    state.next_call_index("escalate")
    result = {"ack": True}
    state.log_audit("agent", "escalate", {"reason": reason}, result)
    return result


def reply_and_close(state: EpisodeState, text: str) -> dict:
    state.next_call_index("reply_and_close")
    result = {"ack": True}
    state.log_audit("agent", "reply_and_close", {"text": text}, result)
    return result


TOOLS = {
    "lookup_order": lookup_order,
    "lookup_customer": lookup_customer,
    "read_policy": read_policy,
    "inspect_refund_history": inspect_refund_history,
    "issue_refund": issue_refund,
    "escalate": escalate,
    "reply_and_close": reply_and_close,
}


def call_tool(state: EpisodeState, tool_name: str, arguments: dict) -> dict:
    if tool_name not in TOOLS:
        raise ToolError(f"unknown tool {tool_name!r}; known: {sorted(TOOLS)}")
    return TOOLS[tool_name](state, **arguments)
