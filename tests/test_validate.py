from trajectory_gym.data.classes import sample
from trajectory_gym.data.validate import (
    MAX_WORDS,
    MIN_WORDS,
    validate_all,
    validate_facts_match_class,
    validate_ticket_body,
)
from trajectory_gym.data.groundtruth import evaluate_policy
from trajectory_gym.models.scenario import Scenario


def _scenario_for(draw, body="x" * 0, ticket_body=None):
    gt = evaluate_policy(draw.facts)
    body_text = ticket_body or (
        "My order arrived and I would like to get in touch about it because something is off "
        "and I am not satisfied with how it turned out overall."
    )
    return Scenario(
        id=f"{draw.scenario_class}-{draw.index:02d}",
        scenario_class=draw.scenario_class,
        persona="terse",
        customer_id=draw.customer_id,
        order_id=draw.order_id,
        ticket_body=body_text,
        ground_truth=gt,
        setup_sql=draw.setup_sql,
        force_stale_status=draw.force_stale_status,
    )


def test_clean_ticket_body_passes():
    body = "My order never arrived and it has been quite a while now, I would like an update please."
    assert validate_ticket_body(body) == []


def test_leak_blocklist_catches_policy_language():
    leaky_bodies = [
        "I read your policy and think I should get a refund within the window.",
        "Please escalate this to a supervisor immediately for a full refund of my order.",
        "I believe I am still eligible for a refund window on this within 30 days.",
        "Isn't there a 60 day return window I should qualify for on this order?",
    ]
    for body in leaky_bodies:
        assert validate_ticket_body(body), f"expected leak detection for: {body!r}"


def test_word_count_bounds():
    too_short = "Refund please."
    assert any("word count" in e for e in validate_ticket_body(too_short))

    too_long = "word " * (MAX_WORDS + 10)
    assert any("word count" in e for e in validate_ticket_body(too_long))

    just_right = "word " * MIN_WORDS
    assert validate_ticket_body(just_right.strip()) == []


def test_validate_facts_match_class_passes_for_correct_sampler_output():
    draw = sample("clean_refundable", 1)
    assert validate_facts_match_class(draw) == []


def test_validate_all_flags_duplicate_scenario_ids():
    draw = sample("clean_refundable", 1)
    scenario = _scenario_for(draw)
    scenario2 = scenario.model_copy()
    errors = validate_all([scenario, scenario2], [draw, draw])
    assert "__global__" in errors
    assert any("duplicate scenario IDs" in e for e in errors["__global__"])
