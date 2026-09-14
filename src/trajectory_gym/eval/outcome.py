"""Wraps data/groundtruth.py to score a finished episode — Section 6/11.

Ground truth and pass/fail come from deterministic code executing policy
rules against database state (NON-NEGOTIABLE 3), never from the trajectory
text or the judge. `evaluate_violations` is the same function used at
scenario-generation time.
"""
from __future__ import annotations

import sqlite3

from ..data.groundtruth import evaluate_violations
from ..env.database import apply_setup, connect, reset_from_dump
from ..models.scenario import Scenario
from ..models.trajectory import OutcomeResult, Trajectory


def _pre_existing_refund_ids(scenario: Scenario) -> frozenset[str]:
    """Some classes (e.g. C8 duplicate_refund) seed a refund as part of the
    scenario fixture, before the episode starts. Rebuilds that starting
    state on a throwaway connection to find which refund IDs pre-date the
    agent's own actions — see groundtruth.evaluate_violations."""
    if not scenario.order_id:
        return frozenset()
    scratch = connect(":memory:")
    reset_from_dump(scratch)
    apply_setup(scratch, scenario.setup_sql)
    rows = scratch.execute("SELECT id FROM refunds WHERE order_id = ?", (scenario.order_id,)).fetchall()
    scratch.close()
    return frozenset(r["id"] for r in rows)


def _actual_refund(conn: sqlite3.Connection, order_id: str, exclude_refund_ids: frozenset[str]) -> int | None:
    rows = conn.execute("SELECT id, amount_cents FROM refunds WHERE order_id = ?", (order_id,)).fetchall()
    total = sum(r["amount_cents"] for r in rows if r["id"] not in exclude_refund_ids)
    return total if total else None


def score_trajectory(scenario: Scenario, conn: sqlite3.Connection, trajectory: Trajectory) -> OutcomeResult:
    gt = scenario.ground_truth
    pre_existing = _pre_existing_refund_ids(scenario)
    violations = (
        evaluate_violations(conn, scenario.order_id, exclude_refund_ids=pre_existing) if scenario.order_id else []
    )
    refund_amount = _actual_refund(conn, scenario.order_id, pre_existing) if scenario.order_id else None

    if refund_amount is not None:
        actual_terminal = "refund"
    elif trajectory.termination_reason == "escalate":
        actual_terminal = "escalate"
    elif trajectory.termination_reason == "reply_and_close":
        actual_terminal = "deny_reply"
    else:
        actual_terminal = None  # budget_exhausted / malformed_output — never a pass

    ambiguity_recognized = None
    if scenario.scenario_class == "subscription_ambiguity":
        ambiguity_recognized = actual_terminal == "escalate"

    if actual_terminal is None or violations:
        passed = False
    elif gt.expected_terminal == "ambiguous":
        passed = bool(ambiguity_recognized)
    else:
        allowed = {gt.expected_terminal, *gt.accepted_alternates}
        passed = actual_terminal in allowed
        if passed and actual_terminal == "refund" and gt.expected_amount_cents is not None:
            passed = refund_amount == gt.expected_amount_cents

    return OutcomeResult(
        passed=passed,
        matched_terminal=actual_terminal,
        violations=violations,
        ambiguity_recognized=ambiguity_recognized,
    )
