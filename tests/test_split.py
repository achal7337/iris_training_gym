from trajectory_gym.data.classes import CLASS_NAMES, sample
from trajectory_gym.data.groundtruth import evaluate_policy
from trajectory_gym.data.split import class_split_indices, make_split
from trajectory_gym.models.scenario import Scenario


def _all_scenarios() -> list[Scenario]:
    scenarios = []
    for cls in CLASS_NAMES:
        for i in range(1, 6):
            draw = sample(cls, i)
            gt = evaluate_policy(draw.facts)
            scenarios.append(
                Scenario(
                    id=f"{cls}-{i:02d}",
                    scenario_class=cls,
                    persona="terse",
                    customer_id=draw.customer_id,
                    order_id=draw.order_id,
                    ticket_body="placeholder ticket body with enough words to pass validation checks easily.",
                    ground_truth=gt,
                    setup_sql=draw.setup_sql,
                    force_stale_status=draw.force_stale_status,
                )
            )
    return scenarios


def test_split_sizes_are_30_dev_20_holdout():
    split_map = make_split(_all_scenarios())
    assert len(split_map["dev"]) == 30
    assert len(split_map["holdout"]) == 20


def test_split_is_stratified_3_2_per_class():
    scenarios = _all_scenarios()
    split_map = make_split(scenarios)
    dev_set = set(split_map["dev"])
    holdout_set = set(split_map["holdout"])
    for cls in CLASS_NAMES:
        class_ids = {s.id for s in scenarios if s.scenario_class == cls}
        assert len(class_ids & dev_set) == 3
        assert len(class_ids & holdout_set) == 2


def test_dev_and_holdout_are_disjoint_and_cover_everything():
    scenarios = _all_scenarios()
    split_map = make_split(scenarios)
    dev_set = set(split_map["dev"])
    holdout_set = set(split_map["holdout"])
    assert dev_set.isdisjoint(holdout_set)
    assert dev_set | holdout_set == {s.id for s in scenarios}


def test_split_is_deterministic_across_calls():
    a = make_split(_all_scenarios())
    b = make_split(_all_scenarios())
    assert a == b


def test_split_does_not_always_put_the_same_index_in_holdout():
    # regression guard: if every class's holdout were always indices {4, 5},
    # a class's fact-variant contrast pair (e.g. C1 partial-return, C5's
    # lone refund case) could end up entirely in one split.
    holdout_index_sets = set()
    for cls in CLASS_NAMES:
        _, holdout_idx = class_split_indices(cls)
        holdout_index_sets.add(tuple(holdout_idx))
    assert len(holdout_index_sets) > 1
