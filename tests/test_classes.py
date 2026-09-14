"""Section 6 tripwire: sampled facts must actually satisfy their class's
predicate. This is the same check validate.py runs at generation time,
pinned here as a regression test."""
import pytest

from trajectory_gym.data.classes import CLASS_NAMES, N_PER_CLASS, all_draws, sample
from trajectory_gym.data.groundtruth import evaluate_policy
from trajectory_gym.data.validate import _EXPECTED_TERMINAL


def test_all_ten_classes_five_each():
    draws = all_draws()
    assert len(draws) == 50
    counts = {}
    for d in draws:
        counts[d.scenario_class] = counts.get(d.scenario_class, 0) + 1
    assert counts == {c: N_PER_CLASS for c in CLASS_NAMES}


@pytest.mark.parametrize("scenario_class", CLASS_NAMES)
def test_class_ground_truth_matches_table(scenario_class):
    for index in range(1, N_PER_CLASS + 1):
        draw = sample(scenario_class, index)
        gt = evaluate_policy(draw.facts)
        allowed = _EXPECTED_TERMINAL[scenario_class]
        assert gt.expected_terminal in allowed, (
            f"{scenario_class} idx={index} -> {gt.expected_terminal}, expected one of {allowed}"
        )


def test_digital_downloaded_has_exactly_one_refund_contrast():
    outcomes = [evaluate_policy(sample("digital_downloaded", i).facts).expected_terminal for i in range(1, 6)]
    assert outcomes.count("refund") == 1
    assert outcomes.count("deny_reply") == 4


def test_clean_refundable_has_partial_and_full_contrast():
    draws = [sample("clean_refundable", i) for i in range(1, 6)]
    full_returns = [d.facts.full_return for d in draws]
    assert full_returns.count(True) == 3
    assert full_returns.count(False) == 2


def test_missing_or_wrong_id_has_resolvable_and_unresolvable_contrast():
    draws = [sample("missing_or_wrong_id", i) for i in range(1, 6)]
    identifiable = [d.facts.order_identifiable for d in draws]
    assert identifiable.count(True) == 3
    assert identifiable.count(False) == 2


def test_sampling_is_deterministic():
    a = sample("gold_tier_trap", 3)
    b = sample("gold_tier_trap", 3)
    assert a.facts == b.facts
    assert a.customer_id == b.customer_id
    assert a.order_id == b.order_id


def test_no_duplicate_order_ids_across_all_draws():
    draws = all_draws()
    order_ids = [d.order_id for d in draws]
    assert len(order_ids) == len(set(order_ids))
