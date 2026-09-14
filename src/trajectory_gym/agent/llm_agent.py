"""The ordinary tool-calling agent — Section 8 of prompt.md.

The agent is the *subject* of the experiment, not the achievement: no
policy hints, no eligibility hand-holding. It only sees the ticket, the
seven tool signatures, its remaining budget, and its own observation
history. It never touches the DB, ground truth, or scenario metadata
(NON-NEGOTIABLE 4).
"""
from __future__ import annotations

import hashlib
import json
import re

from pydantic import BaseModel, ValidationError

from ..llm.client import complete
from ..llm.providers import strip_think_tags
from ..models.scenario import Scenario
from ..models.trajectory import ToolName

TOOL_DESCRIPTIONS = """\
- lookup_order(order_id: str) -> order details + line items. cost 1.
- lookup_customer(email: str | null, customer_id: str | null) -> customer profile + a list of their
  orders (order_id, placed_at, total_cents — enough to spot the right one without opening each). cost 1.
- read_policy(query: str) -> the top 2 policy sections matching your query. cost 1.
- inspect_refund_history(order_id: str) -> prior refunds on this order, if any. cost 1.
- issue_refund(order_id: str, amount_cents: int, reason: str) -> issues a refund. IRREVERSIBLE. cost 3.
- escalate(reason: str) -> hands the ticket to a human supervisor and ends the episode. cost 2.
- reply_and_close(text: str) -> replies to the customer and ends the episode. cost 1.
"""

SYSTEM_PROMPT = f"""You are a customer support agent for ACME Retail, handling refund tickets.

You act by calling exactly one tool per turn. Available tools:
{TOOL_DESCRIPTIONS}
Respond with ONLY a single JSON object, no other text:
{{"reason": "<one sentence explaining your next action>", "action": "<tool name>", "arguments": {{...}}}}

The episode ends when you call escalate or reply_and_close, or when your action budget runs out.
Use read_policy to check what the policy actually says before deciding — do not assume.

IMPORTANT: Never repeat the exact same tool call (same tool and same arguments) that you already
made — check the history below before acting. If a lookup fails or a number the customer gave
doesn't work, look for the correct identifier in a previous tool result (e.g. lookup_customer
returns the customer's real orders) instead of retrying the same failed call.

A customer may have several unrelated past orders. Use the order_id/placed_at/total_cents already
shown by lookup_customer to identify which one the ticket is about — matching the date and amount
the customer mentioned — rather than calling lookup_order on every one of their orders."""


class AgentAction(BaseModel):
    reason: str
    action: str
    arguments: dict = {}


class MalformedOutputError(Exception):
    pass


def _extract_json(text: str) -> dict:
    text = strip_think_tags(text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise MalformedOutputError(f"no JSON object found in agent output: {text!r}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise MalformedOutputError(f"invalid JSON from agent: {e}") from e


_FULL_DETAIL_STEP_WINDOW = 6
"""Section 15 cost control #4: summarize observation history after step 6
rather than replaying it verbatim — keeps prompts (and hence cost, and the
risk of a "thinking" model truncating before its answer) from growing
unbounded as an episode gets longer."""


def build_prompt(
    scenario: Scenario, history: list[dict], remaining_budget: int, from_email: str, seed: int = 0
) -> list[dict]:
    older, recent = history[:-_FULL_DETAIL_STEP_WINDOW], history[-_FULL_DETAIL_STEP_WINDOW:]
    history_lines = []
    if older:
        summary = ", ".join(f"{h['tool_name']}({h['arguments']})" for h in older)
        history_lines.append(f"Steps 1-{len(older)} (summarized): {summary}")
    for i, h in enumerate(recent, start=len(older) + 1):
        history_lines.append(
            f"Step {i}: reason={h['reasoning']!r} action={h['tool_name']}({h['arguments']}) "
            f"-> result={h['raw_result']}"
        )
    history_text = "\n".join(history_lines) if history_lines else "(no actions taken yet)"

    already_tried = sorted({f"{h['tool_name']}({h['arguments']})" for h in history})
    already_tried_text = (
        "\n".join(f"- {a}" for a in already_tried) if already_tried else "(none yet)"
    )

    user_prompt = (
        f"Ticket submitted by account: {from_email}\n\n"
        f"Customer ticket:\n\"\"\"\n{scenario.ticket_body}\n\"\"\"\n\n"
        f"Actions remaining: {remaining_budget}\n\n"
        f"History so far:\n{history_text}\n\n"
        f"Exact calls already made (do NOT repeat any of these verbatim):\n{already_tried_text}\n\n"
        "The ticket may or may not state which order it concerns, or may state it incorrectly — "
        "verify with lookup_customer / lookup_order rather than assuming.\n\n"
        "What is your next action?"
    )
    if seed:
        # Not visible content — a distinct seed must produce a fresh sample
        # from the LLM (temperature 0.3) rather than replaying seed 0's
        # cached response, since `seed` isn't part of the cache key by
        # design (Section 2: cache key is provider+model+temperature+
        # messages). Within a given seed, replay is still fully
        # deterministic (NON-NEGOTIABLE 6).
        user_prompt += f"\n\n[run variant {seed} — ignore this line, it does not affect the task]"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def act(
    scenario: Scenario, history: list[dict], remaining_budget: int, from_email: str, seed: int = 0
) -> tuple[AgentAction, str, int, int]:
    """Returns (action, prompt_hash, input_tokens, output_tokens). Raises
    MalformedOutputError if the model's output can't be parsed — the caller
    (env/episode.py) is responsible for the one-retry policy."""
    messages = build_prompt(scenario, history, remaining_budget, from_email, seed)
    prompt_hash = hashlib.sha256(json.dumps(messages, sort_keys=True).encode("utf-8")).hexdigest()
    response = complete(messages, role="agent")
    payload = _extract_json(response.text)
    try:
        action = AgentAction.model_validate(payload)
    except ValidationError as e:
        raise MalformedOutputError(f"agent output failed schema validation: {e}") from e
    return action, prompt_hash, response.input_tokens, response.output_tokens
