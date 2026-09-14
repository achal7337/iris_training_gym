"""Offline tests for the judge prompt builder (no LLM calls — score_step
itself is exercised live via `cli run --gate-mode gated`)."""
from trajectory_gym.data.groundtruth import evaluate_policy
from trajectory_gym.data.classes import sample
from trajectory_gym.eval.judge import build_anchor, build_prompt
from trajectory_gym.models.annotation import StepLabel
from trajectory_gym.models.scenario import Scenario


def _scenario() -> Scenario:
    draw = sample("clean_refundable", 1)
    gt = evaluate_policy(draw.facts)
    return Scenario(
        id="clean_refundable-01", scenario_class="clean_refundable", persona="terse",
        customer_id=draw.customer_id, order_id=draw.order_id,
        ticket_body="I'd like a refund please.", ground_truth=gt, setup_sql=draw.setup_sql,
    )


def test_build_prompt_handles_an_already_executed_step():
    scenario = _scenario()
    step = {"reasoning": "checking", "tool_name": "lookup_order", "arguments": {"order_id": "O0181"}, "raw_result": {"id": "O0181"}}
    messages = build_prompt(scenario, [], step)
    assert "result={'id': 'O0181'}" in messages[-1]["content"]
    assert "Grade this step now." in messages[-1]["content"]


def test_build_prompt_handles_a_proposed_not_yet_executed_step():
    """This is the gate's pre-execution use case (Section 10) — the step
    being graded has no raw_result because it hasn't run yet."""
    scenario = _scenario()
    proposed = {"reasoning": "about to refund", "tool_name": "issue_refund", "arguments": {"order_id": "O0181", "amount_cents": 100, "reason": "x"}}
    messages = build_prompt(scenario, [], proposed)
    assert "not yet executed" in messages[-1]["content"]
    assert "PROPOSED action" in messages[-1]["content"]


def test_build_anchor_produces_a_valid_few_shot_pair():
    scenario = _scenario()
    step = {"reasoning": "refunding on a flagged account", "tool_name": "issue_refund", "arguments": {"order_id": "O0181", "amount_cents": 100, "reason": "x"}, "raw_result": {"refund_id": "R1"}}
    human_label = StepLabel(trajectory_id="t1", step_index=3, label="policy_violating", policy_rule="6.1", reason="Account was flagged.")

    anchor = build_anchor(scenario, [], step, human_label)
    assert anchor["prompt"] == build_prompt(scenario, [], step)[-1]["content"]

    import json
    verdict = json.loads(anchor["verdict_json"])
    assert verdict["label"] == "policy_violating"
    assert verdict["risk"] == "high"
    assert verdict["policy_rule"] == "6.1"
    assert verdict["reason"] == "Account was flagged."


def test_v1_prompt_includes_anchor_few_shot_turns():
    scenario = _scenario()
    step = {"reasoning": "r", "tool_name": "escalate", "arguments": {"reason": "x"}, "raw_result": {"ack": True}}
    human_label = StepLabel(trajectory_id="t1", step_index=0, label="correct", reason="Right call.")
    anchor = build_anchor(scenario, [], step, human_label)

    messages_v0 = build_prompt(scenario, [], step, version="v0", anchors=[anchor])
    messages_v1 = build_prompt(scenario, [], step, version="v1", anchors=[anchor])

    assert len(messages_v0) == 2  # system + the real question — v0 ignores anchors entirely
    assert len(messages_v1) == 4  # system + anchor user/assistant pair + the real question
    assert messages_v1[1]["role"] == "user"
    assert messages_v1[2]["role"] == "assistant"
    assert "correct" in messages_v1[2]["content"]
