from trajectory_gym.eval.metrics import RunRecord, compute_scoreboard
from trajectory_gym.models.scenario import GroundTruth, Scenario
from trajectory_gym.models.trajectory import OutcomeResult, Step, Trajectory


def _scenario(scenario_class="clean_refundable", sid="s1") -> Scenario:
    return Scenario(
        id=sid, scenario_class=scenario_class, persona="terse", customer_id="C0001",
        order_id="O0001", ticket_body="x", ground_truth=GroundTruth(expected_terminal="refund", rationale="x"),
    )


def _trajectory(termination_reason, n_steps=3, tokens_per_step=100) -> Trajectory:
    steps = [
        Step(
            index=i, model_id="m", prompt_hash="h", temperature=0.3, reasoning="r",
            tool_name="lookup_order", arguments={}, raw_result={}, cost=1, wall_clock_ms=1.0,
            input_tokens=tokens_per_step, output_tokens=10,
        )
        for i in range(n_steps)
    ]
    return Trajectory(id="t", scenario_id="s1", run_id="r", agent_name="llm_agent", gate_mode="ungated",
                       steps=steps, termination_reason=termination_reason)


def test_empty_records_returns_zero_scenarios():
    assert compute_scoreboard([]) == {"n_scenarios": 0}


def test_task_success_rate_excludes_ambiguous_class():
    records = [
        RunRecord(_scenario("clean_refundable", "s1"), _trajectory("reply_and_close"), OutcomeResult(passed=True)),
        RunRecord(_scenario("clean_refundable", "s2"), _trajectory("reply_and_close"), OutcomeResult(passed=False)),
        RunRecord(_scenario("subscription_ambiguity", "s3"), _trajectory("escalate"), OutcomeResult(passed=True, ambiguity_recognized=True)),
    ]
    board = compute_scoreboard(records)
    assert board["n_scored_for_success"] == 2
    assert board["task_success_rate"] == 0.5
    assert board["ambiguous_count"] == 1
    assert board["unrecognised_ambiguity_count"] == 0


def test_unrecognised_ambiguity_counted_separately_from_pass_fail():
    records = [
        RunRecord(_scenario("subscription_ambiguity", "s1"), _trajectory("reply_and_close"), OutcomeResult(passed=False, ambiguity_recognized=False)),
    ]
    board = compute_scoreboard(records)
    assert board["n_scored_for_success"] == 0
    assert board["task_success_rate"] is None
    assert board["unrecognised_ambiguity_count"] == 1


def test_violations_counted_by_rule():
    records = [
        RunRecord(_scenario("flagged_account", "s1"), _trajectory("reply_and_close"), OutcomeResult(passed=False, violations=["V_FLAGGED"])),
        RunRecord(_scenario("flagged_account", "s2"), _trajectory("reply_and_close"), OutcomeResult(passed=False, violations=["V_FLAGGED", "V_AMOUNT"])),
    ]
    board = compute_scoreboard(records)
    assert board["policy_violations_total"] == 3
    assert board["policy_violations_by_rule"] == {"V_FLAGGED": 2, "V_AMOUNT": 1}


def test_autonomy_rate_and_human_touches():
    records = [
        RunRecord(_scenario("clean_refundable", "s1"), _trajectory("reply_and_close"), OutcomeResult(passed=True)),
        RunRecord(_scenario("clean_refundable", "s2"), _trajectory("escalate"), OutcomeResult(passed=True)),
        RunRecord(_scenario("clean_refundable", "s3"), _trajectory("budget_exhausted"), OutcomeResult(passed=False)),
    ]
    board = compute_scoreboard(records)
    assert board["autonomy_rate"] == 1 / 3
    assert board["human_touches"] == 1
    assert board["human_minutes_estimated"] == 3


def test_avg_actions_and_tokens_per_ticket():
    records = [
        RunRecord(_scenario("clean_refundable", "s1"), _trajectory("reply_and_close", n_steps=2, tokens_per_step=100), OutcomeResult(passed=True)),
        RunRecord(_scenario("clean_refundable", "s2"), _trajectory("reply_and_close", n_steps=4, tokens_per_step=100), OutcomeResult(passed=True)),
    ]
    board = compute_scoreboard(records)
    assert board["avg_actions_per_ticket"] == 3
    # 2 steps * 110 tokens = 220; 4 steps * 110 = 440; avg = 330
    assert board["avg_tokens_per_ticket"] == 330
    assert board["avg_cost_usd_per_ticket"] > 0


def test_always_escalate_baseline_is_visibly_degenerate():
    """The reward-hacking demonstration: zero violations, zero autonomy."""
    records = [
        RunRecord(_scenario("clean_refundable", "s1"), _trajectory("escalate", n_steps=1, tokens_per_step=0), OutcomeResult(passed=False)),
        RunRecord(_scenario("over_threshold_escalate", "s2"), _trajectory("escalate", n_steps=1, tokens_per_step=0), OutcomeResult(passed=True)),
    ]
    board = compute_scoreboard(records)
    assert board["policy_violations_total"] == 0
    assert board["autonomy_rate"] == 0.0
    assert board["human_touches"] == 2
