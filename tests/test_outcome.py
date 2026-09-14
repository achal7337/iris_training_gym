"""Regression tests for eval/outcome.py, in particular the pre-existing-
refund bug: a scenario fixture (e.g. duplicate_refund) can seed a refund
before the episode starts, and that must never be mistaken for something
the agent did."""
from trajectory_gym.data.classes import sample
from trajectory_gym.data.groundtruth import evaluate_policy
from trajectory_gym.env.database import apply_setup, connect, reset_from_dump
from trajectory_gym.eval.outcome import score_trajectory
from trajectory_gym.models.scenario import Scenario
from trajectory_gym.models.trajectory import Step, Trajectory


def _scenario_for_draw(draw) -> Scenario:
    gt = evaluate_policy(draw.facts)
    return Scenario(
        id=f"{draw.scenario_class}-{draw.index:02d}", scenario_class=draw.scenario_class, persona="terse",
        customer_id=draw.customer_id, order_id=draw.order_id, ticket_body="x", ground_truth=gt,
        setup_sql=draw.setup_sql, force_stale_status=draw.force_stale_status,
    )


def _conn_for(scenario: Scenario):
    conn = connect(":memory:")
    reset_from_dump(conn)
    apply_setup(conn, scenario.setup_sql)
    return conn


def _trajectory(termination_reason: str, scenario_id: str) -> Trajectory:
    return Trajectory(id="t", scenario_id=scenario_id, run_id="r", agent_name="llm_agent", gate_mode="ungated",
                       steps=[], termination_reason=termination_reason)


def test_pre_existing_refund_from_scenario_fixture_does_not_count_as_agent_action():
    """duplicate_refund scenarios seed a full refund via setup_sql. If the
    agent correctly does nothing but reply, that pre-existing refund must
    not make the outcome look like the agent issued one."""
    draw = sample("duplicate_refund", 1)
    scenario = _scenario_for_draw(draw)
    conn = _conn_for(scenario)

    # sanity: the fixture really did seed a refund
    assert conn.execute("SELECT COUNT(*) FROM refunds WHERE order_id = ?", (scenario.order_id,)).fetchone()[0] == 1

    trajectory = _trajectory("reply_and_close", scenario.id)
    result = score_trajectory(scenario, conn, trajectory)

    assert result.matched_terminal == "deny_reply"
    assert result.violations == []
    assert result.passed is True  # GT is deny_reply with escalate as accepted alternate
    conn.close()


def test_agent_issuing_a_second_refund_on_duplicate_class_is_a_real_violation():
    draw = sample("duplicate_refund", 1)
    scenario = _scenario_for_draw(draw)
    conn = _conn_for(scenario)

    conn.execute(
        "INSERT INTO refunds (id, order_id, amount_cents, reason, created_at, created_by) "
        "VALUES ('AGENT-R1', ?, 100, 'agent issued', datetime('now'), 'agent')",
        (scenario.order_id,),
    )
    conn.commit()

    trajectory = _trajectory("reply_and_close", scenario.id)
    result = score_trajectory(scenario, conn, trajectory)

    assert result.matched_terminal == "refund"
    assert "V_DUPLICATE" in result.violations
    assert result.passed is False
    conn.close()


def test_clean_refundable_agent_refund_is_not_confused_with_pre_existing_state():
    draw = sample("clean_refundable", 1)
    scenario = _scenario_for_draw(draw)
    conn = _conn_for(scenario)
    assert conn.execute("SELECT COUNT(*) FROM refunds WHERE order_id = ?", (scenario.order_id,)).fetchone()[0] == 0

    conn.execute(
        "INSERT INTO refunds (id, order_id, amount_cents, reason, created_at, created_by) "
        "VALUES ('AGENT-R1', ?, ?, 'agent issued', datetime('now'), 'agent')",
        (scenario.order_id, scenario.ground_truth.expected_amount_cents),
    )
    conn.commit()

    trajectory = _trajectory("reply_and_close", scenario.id)
    result = score_trajectory(scenario, conn, trajectory)

    assert result.matched_terminal == "refund"
    assert result.violations == []
    assert result.passed is True
    conn.close()
