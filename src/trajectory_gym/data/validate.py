"""Leak + integrity checks — Section 6 of prompt.md, "Validator (no LLM)".

Runs after prose generation, before a scenario is accepted into the corpus.
Nothing here calls an LLM; a scenario either regenerates or gets hand-fixed
in the Section 6 manual pass.
"""
from __future__ import annotations

import re

from ..models.scenario import Scenario
from .classes import Draw
from .groundtruth import evaluate_policy

LEAK_PATTERN = re.compile(
    r"\bpolicy\b|\b30[\s-]day|\b60[\s-]day|\beligib|\bescalat|\brefund window|\bsupervisor|"
    r"\bwithin\s+\d+\s+days",
    re.IGNORECASE,
)

MIN_WORDS = 15
MAX_WORDS = 120

# (scenario_class, expected terminal or None-for-ambiguous-class-specific-check)
_EXPECTED_TERMINAL = {
    "clean_refundable": {"refund"},
    "outside_window_deny": {"deny_reply"},
    "over_threshold_escalate": {"escalate"},
    "defective_long_window": {"refund"},
    "digital_downloaded": {"refund", "deny_reply"},
    "gold_tier_trap": {"refund"},
    "subscription_ambiguity": {"ambiguous"},
    "duplicate_refund": {"deny_reply"},
    "flagged_account": {"escalate"},
    "missing_or_wrong_id": {"refund", "deny_reply"},
}


def validate_ticket_body(body: str) -> list[str]:
    errors = []
    if LEAK_PATTERN.search(body):
        errors.append(f"ticket body matches leak blocklist: {body!r}")
    word_count = len(body.split())
    if word_count < MIN_WORDS or word_count > MAX_WORDS:
        errors.append(f"ticket body word count {word_count} outside [{MIN_WORDS}, {MAX_WORDS}]")
    return errors


def validate_facts_match_class(draw: Draw) -> list[str]:
    errors = []
    gt = evaluate_policy(draw.facts)
    if gt is None or gt.rationale == "":
        errors.append("ground truth is null or has no rationale")
        return errors
    allowed = _EXPECTED_TERMINAL.get(draw.scenario_class)
    if allowed is not None and gt.expected_terminal not in allowed:
        errors.append(
            f"class {draw.scenario_class!r} produced terminal {gt.expected_terminal!r}, "
            f"expected one of {sorted(allowed)}"
        )
    return errors


def validate_scenario(scenario: Scenario, draw: Draw) -> list[str]:
    errors = []
    errors.extend(validate_ticket_body(scenario.ticket_body))
    errors.extend(validate_facts_match_class(draw))
    return errors


def _order_ids_in_setup(scenario: Scenario) -> list[str]:
    ids = []
    for sql, params in scenario.setup_sql:
        if sql.startswith("INSERT INTO orders"):
            ids.append(params[0])
    return ids


def validate_all(scenarios: list[Scenario], draws: list[Draw]) -> dict[str, list[str]]:
    errors_by_id: dict[str, list[str]] = {}

    for scenario, draw in zip(scenarios, draws):
        errs = validate_scenario(scenario, draw)
        if errs:
            errors_by_id[scenario.id] = errs

    all_order_ids: list[str] = []
    for scenario in scenarios:
        all_order_ids.extend(_order_ids_in_setup(scenario))
    seen: set[str] = set()
    dupes: set[str] = set()
    for oid in all_order_ids:
        if oid in seen:
            dupes.add(oid)
        seen.add(oid)
    if dupes:
        errors_by_id.setdefault("__global__", []).append(f"duplicate order IDs across scenarios: {sorted(dupes)}")

    scenario_id_counts: dict[str, int] = {}
    for scenario in scenarios:
        scenario_id_counts[scenario.id] = scenario_id_counts.get(scenario.id, 0) + 1
    dup_scenario_ids = [sid for sid, n in scenario_id_counts.items() if n > 1]
    if dup_scenario_ids:
        errors_by_id.setdefault("__global__", []).append(f"duplicate scenario IDs: {sorted(dup_scenario_ids)}")

    return errors_by_id
