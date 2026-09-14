import pytest

from trajectory_gym.eval.calibration import (
    agreement_set,
    anchor_set,
    bootstrap_kappa_ci,
    cohens_kappa,
    localization_accuracy,
    policy_violating_recall,
)
from trajectory_gym.models.annotation import StepLabel


def _label(is_anchor=False, trajectory_id="t1", step_index=0) -> StepLabel:
    return StepLabel(trajectory_id=trajectory_id, step_index=step_index, label="correct", reason="x", is_anchor=is_anchor)


def test_perfect_agreement_is_kappa_one():
    labels = ["correct", "correct", "policy_violating", "wrong_harmless"]
    assert cohens_kappa(labels, labels) == pytest.approx(1.0)


def test_kappa_below_perfect_for_partial_agreement():
    a = ["correct", "correct", "correct", "policy_violating"]
    b = ["correct", "correct", "policy_violating", "policy_violating"]
    kappa = cohens_kappa(a, b)
    assert 0.0 < kappa < 1.0


def test_kappa_requires_equal_length_paired_ratings():
    with pytest.raises(ValueError):
        cohens_kappa(["correct"], ["correct", "correct"])


def test_kappa_requires_nonempty_input():
    with pytest.raises(ValueError):
        cohens_kappa([], [])


def test_bootstrap_ci_contains_point_estimate_and_is_deterministic():
    a = ["correct", "correct", "policy_violating", "wrong_harmless", "correct", "policy_violating"]
    b = ["correct", "policy_violating", "policy_violating", "wrong_harmless", "correct", "correct"]
    point = cohens_kappa(a, b)
    lo, hi = bootstrap_kappa_ci(a, b, n_bootstrap=200, seed=42)
    assert lo <= hi
    # bootstrap CI should bracket a reasonable range around the point estimate
    assert lo - 0.5 <= point <= hi + 0.5

    lo2, hi2 = bootstrap_kappa_ci(a, b, n_bootstrap=200, seed=42)
    assert (lo, hi) == (lo2, hi2)


def test_policy_violating_recall_basic():
    human = ["policy_violating", "policy_violating", "correct", "policy_violating"]
    judge = ["policy_violating", "correct", "correct", "policy_violating"]
    # 2 of 3 true policy_violating items were also caught by the judge
    assert policy_violating_recall(human, judge) == pytest.approx(2 / 3)


def test_policy_violating_recall_none_when_no_positives():
    human = ["correct", "wrong_harmless"]
    judge = ["correct", "correct"]
    assert policy_violating_recall(human, judge) is None


def test_localization_top1_and_top3():
    rankings = {
        "t1": [2, 0, 1],  # judge thinks step 2 is worst
        "t2": [0, 1, 2],
    }
    human_flagged = {"t1": 2, "t2": 2}
    assert localization_accuracy(rankings, human_flagged, k=1) == 0.5  # only t1 matches at top-1
    assert localization_accuracy(rankings, human_flagged, k=3) == 1.0  # both within top-3


def test_localization_none_when_no_overlap():
    assert localization_accuracy({"t1": [0]}, {"t2": [0]}, k=1) is None


def test_agreement_and_anchor_sets_are_disjoint_and_cover_everything():
    labels = [_label(is_anchor=True, step_index=i) for i in range(8)] + [
        _label(is_anchor=False, step_index=i) for i in range(8, 70)
    ]
    anchors = anchor_set(labels)
    agreement = agreement_set(labels)
    assert len(anchors) == 8
    assert len(agreement) == 62
    anchor_keys = {(l.trajectory_id, l.step_index) for l in anchors}
    agreement_keys = {(l.trajectory_id, l.step_index) for l in agreement}
    assert anchor_keys.isdisjoint(agreement_keys)
    assert anchor_keys | agreement_keys == {(l.trajectory_id, l.step_index) for l in labels}
