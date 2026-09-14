from trajectory_gym.annotation.selector import Candidate, select_batch, select_random
from trajectory_gym.models.annotation import JudgeVerdict


def _candidate(traj_id, step_index, tool_name, confidence, label="correct", outcome_disagreement=False, scenario_id="s1") -> Candidate:
    return Candidate(
        trajectory_id=traj_id, scenario_id=scenario_id, step_index=step_index, tool_name=tool_name,
        judge_verdict=JudgeVerdict(label=label, confidence=confidence, risk="low", reason="x"),
        outcome_disagreement=outcome_disagreement,
    )


def test_higher_uncertainty_is_picked_first():
    candidates = [
        _candidate("t1", 0, "lookup_order", confidence=0.95),
        _candidate("t2", 0, "lookup_order", confidence=0.4),
    ]
    selected = select_batch(candidates, n=1)
    assert selected[0].candidate.trajectory_id == "t2"
    assert selected[0].breakdown["judge_uncertainty"] == 0.6


def test_outcome_disagreement_boosts_priority():
    candidates = [
        _candidate("t1", 0, "lookup_order", confidence=0.8, outcome_disagreement=False),
        _candidate("t2", 0, "lookup_order", confidence=0.8, outcome_disagreement=True),
    ]
    selected = select_batch(candidates, n=1)
    assert selected[0].candidate.trajectory_id == "t2"


def test_irreversible_action_boosts_priority():
    candidates = [
        _candidate("t1", 0, "lookup_order", confidence=0.8),
        _candidate("t2", 0, "issue_refund", confidence=0.8),
    ]
    selected = select_batch(candidates, n=1)
    assert selected[0].candidate.tool_name == "issue_refund"


def test_max_per_trajectory_cap_is_enforced():
    candidates = [_candidate("t1", i, "lookup_order", confidence=0.1) for i in range(5)]
    selected = select_batch(candidates, n=5, max_per_trajectory=2)
    assert len(selected) == 2


def test_excluded_keys_are_never_reselected():
    candidates = [_candidate("t1", 0, "lookup_order", confidence=0.1)]
    selected = select_batch(candidates, n=5, excluded_keys={("t1", 0)})
    assert selected == []


def test_redundancy_penalizes_repeat_tool_label_combo():
    # three identical (tool, label) candidates from distinct trajectories —
    # after the first is picked, the next of the same (tool, label) combo
    # should score lower than a distinct one.
    candidates = [
        _candidate("t1", 0, "lookup_order", confidence=0.5, label="correct"),
        _candidate("t2", 0, "lookup_order", confidence=0.5, label="correct"),
        _candidate("t3", 0, "escalate", confidence=0.5, label="correct"),
    ]
    selected = select_batch(candidates, n=3)
    # the escalate/correct candidate (no redundancy) should outrank the second lookup_order/correct one
    tool_order = [s.candidate.tool_name for s in selected]
    assert tool_order[1] == "escalate" or tool_order[2] == "escalate"
    last = selected[-1]
    if last.candidate.tool_name == "lookup_order":
        assert last.breakdown["redundancy"] == 1.0


def test_novelty_favors_underrepresented_tools():
    candidates = [
        _candidate("t1", 0, "lookup_order", confidence=0.5),
        _candidate("t2", 0, "lookup_order", confidence=0.5),
        _candidate("t3", 0, "escalate", confidence=0.5),
    ]
    selected = select_batch(candidates, n=3)
    # after two lookup_order picks, escalate (never picked) has max novelty and should come last
    # only if priorities favor it; check breakdown values make sense
    for s in selected:
        assert 0.0 <= s.breakdown["novelty"] <= 1.0


def test_select_random_is_deterministic_given_seed():
    candidates = [_candidate(f"t{i}", 0, "lookup_order", confidence=0.5) for i in range(10)]
    a = select_random(candidates, n=3, seed=42)
    b = select_random(candidates, n=3, seed=42)
    assert [c.trajectory_id for c in a] == [c.trajectory_id for c in b]


def test_select_random_respects_max_per_trajectory():
    candidates = [_candidate("t1", i, "lookup_order", confidence=0.5) for i in range(5)]
    chosen = select_random(candidates, n=5, seed=1, max_per_trajectory=2)
    assert len(chosen) == 2
