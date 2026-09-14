"""Offline regression tests for the step loop (env/episode.py). The agent
and judge are monkeypatched with scripted behavior so these never touch the
network — the live-LLM behavior is exercised manually via `cli run`, not
here."""
from __future__ import annotations

import pytest

from trajectory_gym.agent import llm_agent
from trajectory_gym.config import GateConfig, get_gate_config
from trajectory_gym.env import episode
from trajectory_gym.eval import judge as judge_module
from trajectory_gym.models.annotation import JudgeVerdict
from trajectory_gym.models.scenario import GroundTruth, Scenario


def _scenario(scenario_class="clean_refundable", order_id="O0001", customer_id="C0004") -> Scenario:
    return Scenario(
        id="test-scenario-01",
        scenario_class=scenario_class,
        persona="terse",
        customer_id=customer_id,
        order_id=order_id,
        ticket_body="I'd like a refund for my order please, it arrived recently.",
        ground_truth=GroundTruth(expected_terminal="refund", expected_amount_cents=17676, rationale="test"),
        setup_sql=[],
    )


def _script_agent(monkeypatch, actions: list[llm_agent.AgentAction]):
    calls = iter(actions)

    def fake_act(scenario, history, remaining_budget, from_email, seed=0):
        return next(calls), "fakehash", 10, 5

    monkeypatch.setattr(episode.llm_agent, "act", fake_act)


def test_trajectory_id_and_seed_are_unique_across_seeds(monkeypatch):
    """Regression test: without a seed in the trajectory id, two seeds of
    the same scenario would collide (same id) and the UI/analysis couldn't
    tell them apart."""
    _script_agent(monkeypatch, [
        llm_agent.AgentAction(reason="close", action="reply_and_close", arguments={"text": "done"}),
        llm_agent.AgentAction(reason="close", action="reply_and_close", arguments={"text": "done"}),
    ])
    scenario = _scenario()
    t0, conn0 = episode.run_episode(scenario, run_id="t1", gate_config=get_gate_config(), seed=0)
    t1, conn1 = episode.run_episode(scenario, run_id="t1", gate_config=get_gate_config(), seed=1)
    assert t0.seed == 0
    assert t1.seed == 1
    assert t0.id != t1.id
    conn0.close()
    conn1.close()


def test_reply_and_close_terminates_cleanly(monkeypatch):
    _script_agent(monkeypatch, [
        llm_agent.AgentAction(reason="just close it", action="reply_and_close", arguments={"text": "done"}),
    ])
    scenario = _scenario()
    trajectory, conn = episode.run_episode(scenario, run_id="t1", gate_config=get_gate_config())
    assert trajectory.termination_reason == "reply_and_close"
    assert len(trajectory.steps) == 1
    assert trajectory.steps[0].raw_result == {"ack": True}
    conn.close()


def test_budget_exhausted_records_the_unaffordable_attempt(monkeypatch):
    # lookup_order x7 (cost 7) leaves 1 remaining, then an attempted
    # issue_refund (cost 3) can't be afforded.
    actions = [
        llm_agent.AgentAction(reason="check", action="lookup_order", arguments={"order_id": "O0001"})
        for _ in range(7)
    ] + [llm_agent.AgentAction(reason="refund now", action="issue_refund", arguments={"order_id": "O0001", "amount_cents": 100, "reason": "x"})]
    _script_agent(monkeypatch, actions)
    scenario = _scenario()
    trajectory, conn = episode.run_episode(scenario, run_id="t2", gate_config=get_gate_config())

    assert trajectory.termination_reason == "budget_exhausted"
    assert len(trajectory.steps) == 8  # 7 executed lookups + 1 recorded-but-unaffordable attempt
    last = trajectory.steps[-1]
    assert last.tool_name == "issue_refund"
    assert last.raw_result["error"] == "BUDGET_EXCEEDED"
    assert last.cost == 0
    # the refund must never have actually been issued
    assert conn.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 0
    conn.close()


def test_malformed_output_retries_once_then_terminates(monkeypatch):
    call_count = {"n": 0}

    def fake_act(scenario, history, remaining_budget, from_email, seed=0):
        call_count["n"] += 1
        raise llm_agent.MalformedOutputError("bad json")

    monkeypatch.setattr(episode.llm_agent, "act", fake_act)
    scenario = _scenario()
    trajectory, conn = episode.run_episode(scenario, run_id="t3", gate_config=get_gate_config())

    assert trajectory.termination_reason == "malformed_output"
    assert len(trajectory.steps) == 0
    assert call_count["n"] == 2  # one retry, per Section 8
    conn.close()


def test_gate_blocks_issue_refund_when_judge_says_policy_violating(monkeypatch):
    _script_agent(monkeypatch, [
        llm_agent.AgentAction(
            reason="refund it", action="issue_refund",
            arguments={"order_id": "O0001", "amount_cents": 100, "reason": "customer request"},
        ),
        llm_agent.AgentAction(reason="ok escalate then", action="escalate", arguments={"reason": "blocked, escalating"}),
    ])
    monkeypatch.setattr(
        judge_module, "score_step",
        lambda *a, **kw: JudgeVerdict(label="policy_violating", confidence=0.9, risk="high", reason="looks wrong"),
    )
    scenario = _scenario()
    gate_config = get_gate_config().model_copy(update={"mode": "gated", "tau": 0.5})
    trajectory, conn = episode.run_episode(scenario, run_id="t4", gate_config=gate_config)

    assert trajectory.steps[0].tool_name == "issue_refund"
    assert trajectory.steps[0].raw_result["error"] == "BLOCKED"
    assert trajectory.steps[0].gate_verdict.blocked is True
    assert conn.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 0
    assert trajectory.termination_reason == "escalate"
    conn.close()


def test_second_gate_block_forces_escalate(monkeypatch):
    _script_agent(monkeypatch, [
        llm_agent.AgentAction(
            reason="refund it", action="issue_refund",
            arguments={"order_id": "O0001", "amount_cents": 100, "reason": "customer request"},
        ),
        llm_agent.AgentAction(
            reason="try again", action="issue_refund",
            arguments={"order_id": "O0001", "amount_cents": 100, "reason": "customer request, retry"},
        ),
    ])
    monkeypatch.setattr(
        judge_module, "score_step",
        lambda *a, **kw: JudgeVerdict(label="policy_violating", confidence=0.9, risk="high", reason="still looks wrong"),
    )
    scenario = _scenario()
    gate_config = get_gate_config().model_copy(update={"mode": "gated", "tau": 0.5})
    trajectory, conn = episode.run_episode(scenario, run_id="t6", gate_config=gate_config)

    assert len(trajectory.steps) == 3
    assert trajectory.steps[0].raw_result["error"] == "BLOCKED"
    assert trajectory.steps[1].raw_result["error"] == "BLOCKED"
    assert trajectory.steps[2].tool_name == "escalate"
    assert trajectory.steps[2].raw_result == {"ack": True}
    assert trajectory.termination_reason == "escalate"
    assert conn.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 0
    conn.close()


def test_always_escalate_baseline_resolves_in_one_step_with_no_llm_call(monkeypatch):
    def fail_if_called(*a, **kw):
        raise AssertionError("always_escalate must never call the LLM agent")

    monkeypatch.setattr(episode.llm_agent, "act", fail_if_called)
    scenario = _scenario()
    trajectory, conn = episode.run_episode(
        scenario, run_id="t7", gate_config=get_gate_config(), agent_name="always_escalate"
    )
    assert trajectory.agent_name == "always_escalate"
    assert trajectory.termination_reason == "escalate"
    assert len(trajectory.steps) == 1
    assert trajectory.steps[0].tool_name == "escalate"
    assert trajectory.steps[0].input_tokens == 0
    conn.close()


def test_different_seeds_can_produce_different_prompts():
    scenario = _scenario()
    messages_seed0 = llm_agent.build_prompt(scenario, [], 8, "a@example.com", seed=0)
    messages_seed1 = llm_agent.build_prompt(scenario, [], 8, "a@example.com", seed=1)
    assert messages_seed0 != messages_seed1
    # same seed -> byte-identical prompt (determinism within a seed)
    messages_seed1_again = llm_agent.build_prompt(scenario, [], 8, "a@example.com", seed=1)
    assert messages_seed1 == messages_seed1_again


def test_gate_does_not_block_in_ungated_mode(monkeypatch):
    _script_agent(monkeypatch, [
        llm_agent.AgentAction(
            reason="refund it", action="issue_refund",
            arguments={"order_id": "O0001", "amount_cents": 100, "reason": "customer request"},
        ),
        llm_agent.AgentAction(reason="confirm to customer", action="reply_and_close", arguments={"text": "refunded"}),
    ])
    monkeypatch.setattr(
        judge_module, "score_step",
        lambda *a, **kw: JudgeVerdict(label="policy_violating", confidence=0.99, risk="high", reason="looks wrong"),
    )
    scenario = _scenario()
    gate_config = get_gate_config().model_copy(update={"mode": "ungated"})
    trajectory, conn = episode.run_episode(scenario, run_id="t5", gate_config=gate_config)

    assert trajectory.steps[0].raw_result.get("error") != "BLOCKED"
    assert conn.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 1
    conn.close()
