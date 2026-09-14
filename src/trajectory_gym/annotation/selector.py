"""Active step selector — Section 9 of prompt.md.

priority = 1.0 * judge_uncertainty
         + 1.5 * outcome_disagreement   # trajectory failed but judge scored all steps clean
         + 1.2 * irreversibility        # step is an issue_refund
         + 0.5 * novelty                # under-represented tool/step-type in labelled set
         - 1.0 * redundancy             # near-duplicate of an already-labelled step

Cap 2 steps per trajectory. Each selection carries a plain-language
breakdown for the Review page ("why this step").
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models.annotation import JudgeVerdict

WEIGHTS = {
    "judge_uncertainty": 1.0,
    "outcome_disagreement": 1.5,
    "irreversibility": 1.2,
    "novelty": 0.5,
    "redundancy": -1.0,
}

IRREVERSIBLE_TOOLS = {"issue_refund"}


@dataclass
class Candidate:
    trajectory_id: str
    scenario_id: str
    step_index: int
    tool_name: str
    judge_verdict: JudgeVerdict
    outcome_disagreement: bool


@dataclass
class Selection:
    candidate: Candidate
    priority: float
    breakdown: dict[str, float]
    explanation: str


def _explain(breakdown: dict[str, float]) -> str:
    parts = []
    if breakdown["judge_uncertainty"] > 0:
        contrib = breakdown["judge_uncertainty"] * WEIGHTS["judge_uncertainty"]
        parts.append(f"Judge is unsure ({breakdown['judge_uncertainty']:.2f}, +{contrib:.2f}).")
    if breakdown["outcome_disagreement"] > 0:
        parts.append(f"This trajectory failed but the judge marked every step clean (+{WEIGHTS['outcome_disagreement']:.2f}).")
    if breakdown["irreversibility"] > 0:
        parts.append(f"Irreversible action (+{WEIGHTS['irreversibility']:.2f}).")
    if breakdown["novelty"] > 0:
        contrib = breakdown["novelty"] * WEIGHTS["novelty"]
        parts.append(f"Under-represented tool in the labeled set so far (+{contrib:.2f}).")
    if breakdown["redundancy"] > 0:
        contrib = breakdown["redundancy"] * WEIGHTS["redundancy"]
        parts.append(f"Near-duplicate of an already-labeled step ({contrib:.2f}).")
    return " ".join(parts) if parts else "Baseline priority — nothing unusual about this step."


def _score(candidate: Candidate, tool_counts: dict[str, int], total_selected: int, dup_keys: set[tuple[str, str]]) -> Selection:
    judge_uncertainty = 1.0 - candidate.judge_verdict.confidence
    outcome_disagreement = 1.0 if candidate.outcome_disagreement else 0.0
    irreversibility = 1.0 if candidate.tool_name in IRREVERSIBLE_TOOLS else 0.0
    tool_count = tool_counts.get(candidate.tool_name, 0)
    novelty = 1.0 - (tool_count / total_selected) if total_selected else 1.0
    dup_key = (candidate.tool_name, candidate.judge_verdict.label)
    redundancy = 1.0 if dup_key in dup_keys else 0.0

    breakdown = {
        "judge_uncertainty": judge_uncertainty,
        "outcome_disagreement": outcome_disagreement,
        "irreversibility": irreversibility,
        "novelty": novelty,
        "redundancy": redundancy,
    }
    priority = sum(WEIGHTS[k] * v for k, v in breakdown.items())
    return Selection(candidate=candidate, priority=priority, breakdown=breakdown, explanation=_explain(breakdown))


def select_batch(
    candidates: list[Candidate],
    n: int,
    excluded_keys: set[tuple[str, int]] = frozenset(),
    max_per_trajectory: int = 2,
) -> list[Selection]:
    """Greedily picks the highest-priority remaining candidate, one at a
    time, recomputing novelty/redundancy against what's been picked so far
    in this batch — the whole point of an *active* selector."""
    pool = [c for c in candidates if (c.trajectory_id, c.step_index) not in excluded_keys]
    selected: list[Selection] = []
    tool_counts: dict[str, int] = {}
    dup_keys: set[tuple[str, str]] = set()
    per_traj_count: dict[str, int] = {}

    while pool and len(selected) < n:
        scored = [
            _score(c, tool_counts, len(selected), dup_keys)
            for c in pool
            if per_traj_count.get(c.trajectory_id, 0) < max_per_trajectory
        ]
        if not scored:
            break
        best = max(scored, key=lambda s: s.priority)
        selected.append(best)
        pool.remove(best.candidate)
        per_traj_count[best.candidate.trajectory_id] = per_traj_count.get(best.candidate.trajectory_id, 0) + 1
        tool_counts[best.candidate.tool_name] = tool_counts.get(best.candidate.tool_name, 0) + 1
        dup_keys.add((best.candidate.tool_name, best.candidate.judge_verdict.label))

    return selected


def select_random(
    candidates: list[Candidate],
    n: int,
    seed: int,
    excluded_keys: set[tuple[str, int]] = frozenset(),
    max_per_trajectory: int = 2,
) -> list[Candidate]:
    """The random baseline (Section 9): label N actively-selected and N
    randomly-selected steps, compare judge kappa built from each."""
    import random

    pool = [c for c in candidates if (c.trajectory_id, c.step_index) not in excluded_keys]
    rng = random.Random(seed)
    rng.shuffle(pool)
    chosen: list[Candidate] = []
    per_traj_count: dict[str, int] = {}
    for c in pool:
        if len(chosen) >= n:
            break
        if per_traj_count.get(c.trajectory_id, 0) >= max_per_trajectory:
            continue
        chosen.append(c)
        per_traj_count[c.trajectory_id] = per_traj_count.get(c.trajectory_id, 0) + 1
    return chosen
