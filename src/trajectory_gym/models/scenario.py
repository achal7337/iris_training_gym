"""Scenario and ground-truth records — Section 6 of prompt.md.

Ground truth is derived by the rule engine executing against sampled DB
facts, never by an LLM (NON-NEGOTIABLE 3). A Scenario carries the ground
truth, but the agent is never shown it (NON-NEGOTIABLE 4).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

ScenarioClass = Literal[
    "clean_refundable",
    "outside_window_deny",
    "over_threshold_escalate",
    "defective_long_window",
    "digital_downloaded",
    "gold_tier_trap",
    "subscription_ambiguity",
    "duplicate_refund",
    "flagged_account",
    "missing_or_wrong_id",
]

Terminal = Literal["refund", "escalate", "deny_reply", "ambiguous"]

ViolationPredicate = Literal[
    "V_THRESHOLD",
    "V_WINDOW",
    "V_DIGITAL",
    "V_DUPLICATE",
    "V_FLAGGED",
    "V_SHIPPING",
    "V_AMOUNT",
]

Persona = Literal[
    "angry", "confused", "terse", "rambling", "over_detailed", "polite_formal"
]


class GroundTruth(BaseModel):
    expected_terminal: Terminal
    expected_amount_cents: Optional[int] = None
    accepted_alternates: list[Terminal] = []
    violation_predicates: list[ViolationPredicate] = []
    rationale: str


class Scenario(BaseModel):
    id: str
    scenario_class: ScenarioClass
    persona: Persona
    customer_id: str
    order_id: Optional[str] = None
    ticket_body: str
    ground_truth: GroundTruth
    setup_sql: list[tuple[str, list]] = []
    """(sql, params) pairs applied after `reset_from_dump`, before the
    episode starts, to instantiate this scenario's exact facts on top of
    the base world (Section 6: "sample facts under constraints that
    guarantee the class"). Replaying these is what makes a scenario
    deterministic."""
    force_stale_status: bool = False
    """C10 forces the first `lookup_order` stale-injection roll rather than
    leaving it to the usual 10% chance (Section 6)."""
