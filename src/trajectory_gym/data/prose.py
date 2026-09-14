"""The ticket writer — the only LLM call in the data pipeline (Section 6).

Writes only what the customer would plausibly say: never the resolution,
never policy/eligibility/window/escalation language. `validate.py` enforces
the leak blocklist after the fact; this prompt is the first line of defense.
"""
from __future__ import annotations

import random
import re

from ..llm.client import complete
from .classes import Draw

PERSONAS = ["angry", "confused", "terse", "rambling", "over_detailed", "polite_formal"]

_SITUATION = {
    "clean_refundable": "The customer received an item and wants to send it back for a refund.",
    "outside_window_deny": "The customer received an item and wants to send it back for a refund.",
    "over_threshold_escalate": "The customer received an item and wants to send it back for a refund.",
    "defective_long_window": "The customer wants a refund because the item they received is defective or broken.",
    "digital_downloaded": "The customer wants a refund for a digital purchase they made.",
    "gold_tier_trap": "The customer received an item and wants to send it back for a refund.",
    "subscription_ambiguity": "The customer wants a refund for a recent charge on their recurring subscription.",
    "duplicate_refund": "The customer is writing in again asking about a refund for this order.",
    "flagged_account": "The customer received an item and wants to send it back for a refund.",
    "missing_or_wrong_id": "The customer received an item and wants to send it back for a refund.",
}

_PERSONA_STYLE = {
    "angry": "Angry and frustrated. Short, sharp sentences. May use exclamation points.",
    "confused": "Confused and unsure of the details. Hedges a lot (\"I think\", \"maybe\").",
    "terse": "Terse. One or two short sentences, minimal detail.",
    "rambling": "Rambling. Includes some unrelated small talk or tangents before getting to the point.",
    "over_detailed": "Over-detailed. Includes excessive specifics most of which are irrelevant.",
    "polite_formal": "Polite and formal, like a written business email.",
}

_SYSTEM_PROMPT = """You are role-playing as a retail customer writing a short support message \
about an order. Write ONLY the message the customer would send. Follow these rules strictly:

- HARD LIMIT: 30-100 words. Count your words before answering. A message over 100 words is a \
failure. 2-4 short sentences is plenty — do not pad with extra tangents to fill space.
- Never state or imply what the correct resolution should be (do not say whether you deserve \
a refund, whether it should be approved, or what should happen).
- Never say the words "policy", "eligible"/"eligibility", "escalate", "supervisor", or mention \
a specific number of days (e.g. "30 days") or a return/refund "window".
- Do not mention the customer's membership tier or account status.
- Stick to the situation described below — do not invent a different kind of complaint
  (e.g. a missing or late item) than the one given.
- Never use bracketed placeholder text like "[item name]" — invent a plausible, generic
  product description instead (e.g. "the headphones", "the desk lamp").
- Output only the message text, with no preamble, quotes, or signature."""


def _persona_for(scenario_class: str, index: int) -> str:
    # deterministic from the same (class, index) seed used to sample facts
    rng = random.Random(f"42|persona|{scenario_class}|{index}")
    return rng.choice(PERSONAS)


def _include_inaccuracy(scenario_class: str, index: int) -> bool:
    rng = random.Random(f"42|inaccuracy|{scenario_class}|{index}")
    return rng.random() < (1 / 3)


def build_prompt(draw: Draw, persona: str, include_inaccuracy: bool) -> list[dict]:
    facts_lines = [
        f"- Situation: {_SITUATION[draw.scenario_class]}",
        f"- Item type: {draw.facts.item_type}",
        f"- Order total: ${draw.facts.total_cents / 100:.2f}",
    ]
    if draw.facts.defect_reported:
        facts_lines.append("- The item is defective / broken / stopped working")
    facts_lines.extend(f"- {h}" for h in draw.ticket_hints)

    inaccuracy_line = (
        "\nGet one small detail slightly wrong — an approximate/incorrect date, a wrong order "
        "number, or a misremembered amount. This should read as an honest mistake, not a lie."
        if include_inaccuracy
        else ""
    )

    user_prompt = (
        f"Persona / tone: {_PERSONA_STYLE[persona]}\n\n"
        f"Facts you (the customer) know and may reference naturally:\n"
        + "\n".join(facts_lines)
        + inaccuracy_line
        + "\n\nWrite the customer's support message now."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _clean(text: str) -> str:
    body = text.strip()
    body = re.sub(r'^"|"$', "", body).strip()
    return body


def write_ticket(draw: Draw, max_attempts: int = 4) -> tuple[str, str]:
    """Returns (ticket_body, persona). Retries with an escalating corrective
    instruction if the response trips the leak/length validator — a fresh
    instruction text changes the cache key, so retries aren't just replaying
    the same cached (bad) response."""
    from .validate import validate_ticket_body  # local import: avoids a cycle at module load

    persona = _persona_for(draw.scenario_class, draw.index)
    include_inaccuracy = _include_inaccuracy(draw.scenario_class, draw.index)
    messages = build_prompt(draw, persona, include_inaccuracy)

    body = ""
    for attempt in range(max_attempts):
        response = complete(messages, role="writer")
        body = _clean(response.text)
        errors = validate_ticket_body(body)
        if not errors:
            break
        word_count = len(body.split())
        correction = (
            f"\n\n[Revision needed — attempt {attempt + 2}: your previous draft had {word_count} "
            "words and/or used a forbidden word. Rewrite from scratch, strictly under 100 words, "
            "and remove any mention of policy/eligibility/days/window/escalate/supervisor.]"
        )
        messages = messages[:-1] + [{"role": messages[-1]["role"], "content": messages[-1]["content"] + correction}]

    return body, persona
