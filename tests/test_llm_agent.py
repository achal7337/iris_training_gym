from trajectory_gym.agent.llm_agent import AgentAction, MalformedOutputError, _extract_json, build_prompt
from trajectory_gym.data.classes import sample
from trajectory_gym.data.groundtruth import evaluate_policy
from trajectory_gym.models.scenario import Scenario
import pytest


def _scenario() -> Scenario:
    draw = sample("clean_refundable", 1)
    gt = evaluate_policy(draw.facts)
    return Scenario(
        id="clean_refundable-01", scenario_class="clean_refundable", persona="terse",
        customer_id=draw.customer_id, order_id=draw.order_id, ticket_body="x", ground_truth=gt,
        setup_sql=draw.setup_sql,
    )


def _step(i: int) -> dict:
    return {"reasoning": f"reason {i}", "tool_name": "lookup_order", "arguments": {"order_id": f"O{i}"}, "raw_result": {"ok": i}}


def test_extract_json_plain():
    payload = _extract_json('{"reason": "x", "action": "escalate", "arguments": {}}')
    assert payload["action"] == "escalate"


def test_extract_json_strips_thinking_block_with_example_json_inside():
    """Regression test: Qwen3's inline <think>...</think> reasoning can
    contain example/quoted JSON (e.g. while explaining what it's about to
    output), which would confuse a naive greedy {...} extraction spanning
    from the first brace inside the thinking block to the last brace at the
    very end."""
    text = (
        "<think>\n"
        "The user wants me to call escalate. I should output something like "
        '{"reason": "wrong example", "action": "reply_and_close"} but actually '
        "I will escalate instead.\n"
        "</think>\n\n"
        '{"reason": "flagged account", "action": "escalate", "arguments": {"reason": "flagged"}}'
    )
    payload = _extract_json(text)
    assert payload["action"] == "escalate"
    assert payload["reason"] == "flagged account"


def test_extract_json_raises_on_think_only_no_answer():
    with pytest.raises(MalformedOutputError):
        _extract_json("<think>still thinking, ran out of tokens before answering")


def test_history_within_window_is_shown_in_full():
    scenario = _scenario()
    history = [_step(i) for i in range(1, 4)]  # 3 steps, under the 6-step window
    messages = build_prompt(scenario, history, 5, "a@example.com")
    content = messages[-1]["content"]
    assert "summarized" not in content
    for i in range(1, 4):
        assert f"reason {i}" in content


def test_history_beyond_window_is_summarized():
    scenario = _scenario()
    history = [_step(i) for i in range(1, 9)]  # 8 steps, 2 beyond the 6-step window
    messages = build_prompt(scenario, history, 0, "a@example.com")
    content = messages[-1]["content"]
    assert "Steps 1-2 (summarized)" in content
    assert "reason 1" not in content  # summarized away
    assert "reason 2" not in content
    for i in range(3, 9):
        assert f"reason {i}" in content  # last 6 stay in full detail
