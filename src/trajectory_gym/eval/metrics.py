"""The scoreboard — Section 11 of prompt.md. Judge kappa, policy_violating
recall, and localization need human labels (Phase 5) and are added there;
this covers the metrics computable from outcome + trajectory data alone.

Outcome (categorical) and cost (real units) are reported as separate
numbers, never folded into one weighted score — see docs/reward_design.md,
"Why outcome and cost are never summed into one scalar."
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models.scenario import Scenario
from ..models.trajectory import OutcomeResult, Trajectory

# A flat blended rate for cheap open-weight models, not a per-provider price
# table. Good enough for an order-of-magnitude $/ticket figure; replace with
# real per-provider pricing if this number needs to be defensible to a cent.
APPROX_COST_PER_1K_TOKENS = 0.0002
HUMAN_MINUTES_PER_TOUCH = 3


@dataclass
class RunRecord:
    scenario: Scenario
    trajectory: Trajectory
    outcome: OutcomeResult


def compute_scoreboard(records: list[RunRecord]) -> dict:
    if not records:
        return {"n_scenarios": 0}

    # C7 (subscription_ambiguity) is scored separately and never counted in
    # pass/fail — Section 6.
    scored = [r for r in records if r.scenario.scenario_class != "subscription_ambiguity"]
    ambiguous = [r for r in records if r.scenario.scenario_class == "subscription_ambiguity"]

    task_success_rate = (sum(r.outcome.passed for r in scored) / len(scored)) if scored else None

    violations_by_rule: dict[str, int] = {}
    for r in records:
        for v in r.outcome.violations:
            violations_by_rule[v] = violations_by_rule.get(v, 0) + 1

    unrecognised_ambiguity_count = sum(1 for r in ambiguous if not r.outcome.ambiguity_recognized)

    n = len(records)
    human_touches = sum(1 for r in records if r.trajectory.termination_reason == "escalate")
    autonomy_rate = sum(1 for r in records if r.trajectory.termination_reason == "reply_and_close") / n

    avg_actions_per_ticket = sum(len(r.trajectory.steps) for r in records) / n
    tokens_per_ticket = [sum(s.input_tokens + s.output_tokens for s in r.trajectory.steps) for r in records]
    avg_tokens_per_ticket = sum(tokens_per_ticket) / n
    avg_cost_usd_per_ticket = avg_tokens_per_ticket / 1000 * APPROX_COST_PER_1K_TOKENS

    return {
        "n_scenarios": n,
        "n_scored_for_success": len(scored),
        "task_success_rate": task_success_rate,
        "policy_violations_total": sum(violations_by_rule.values()),
        "policy_violations_by_rule": violations_by_rule,
        "ambiguous_count": len(ambiguous),
        "unrecognised_ambiguity_count": unrecognised_ambiguity_count,
        "autonomy_rate": autonomy_rate,
        "human_touches": human_touches,
        "human_minutes_estimated": human_touches * HUMAN_MINUTES_PER_TOUCH,
        "avg_actions_per_ticket": avg_actions_per_ticket,
        "avg_tokens_per_ticket": avg_tokens_per_ticket,
        "avg_cost_usd_per_ticket": avg_cost_usd_per_ticket,
    }
