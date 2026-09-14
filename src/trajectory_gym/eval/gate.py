"""Pre-execution gate — Section 10 of prompt.md.

Fires only before an irreversible action executes (in practice: only
`issue_refund`, per config/gate.yaml). The judge scores the *proposed*
action before it runs; if it comes back `policy_violating` with confidence
above tau, the call is blocked and the agent sees `BLOCKED: <reason>` as
the tool result instead of the refund actually happening.

`outcome_oracle` mode (Section 11's "outcome-only judge" configuration)
replaces the LLM judge with the deterministic rule engine itself — zero
annotation cost, zero LLM calls — to show directly whether calibrating a
judge earned anything over just hard-coding the rules into the gate.
"""
from __future__ import annotations

import sqlite3

from ..config import GateConfig
from ..data import groundtruth
from ..models.annotation import JudgeVerdict
from ..models.scenario import Scenario
from ..models.trajectory import GateVerdict
from . import judge as judge_module


def _oracle_verdict(conn: sqlite3.Connection, proposed_step: dict) -> JudgeVerdict:
    order_id = proposed_step["arguments"]["order_id"]
    amount_cents = proposed_step["arguments"]["amount_cents"]
    violations = groundtruth.evaluate_proposed_refund(conn, order_id, amount_cents)
    if violations:
        return JudgeVerdict(
            label="policy_violating", confidence=1.0, risk="high",
            policy_rule=",".join(violations), reason=f"Rule engine: would trigger {violations}.",
        )
    return JudgeVerdict(label="correct", confidence=1.0, risk="low", reason="Rule engine: no violation predicate fires.")


def check_gate(
    scenario: Scenario,
    steps_before: list[dict],
    proposed_step: dict,
    gate_config: GateConfig,
    conn: sqlite3.Connection | None = None,
) -> GateVerdict:
    action = proposed_step["tool_name"]

    if gate_config.mode == "ungated":
        return GateVerdict(blocked=False)

    if action not in gate_config.irreversible_actions:
        return GateVerdict(blocked=False)

    if gate_config.mode == "outcome_oracle":
        if conn is None:
            raise ValueError("outcome_oracle gate mode requires a live db connection")
        verdict = _oracle_verdict(conn, proposed_step)
    else:
        verdict = judge_module.score_step(scenario, steps_before, proposed_step, version="v0")

    if gate_config.mode == "human_first":
        # No interactive approval channel yet (Phase 5 cut-list item 7) —
        # every irreversible action is blocked pending a human.
        return GateVerdict(blocked=True, judge=verdict)

    p_policy_violating = verdict.confidence if verdict.label == "policy_violating" else 0.0
    blocked = p_policy_violating > gate_config.tau
    return GateVerdict(blocked=blocked, judge=verdict)
