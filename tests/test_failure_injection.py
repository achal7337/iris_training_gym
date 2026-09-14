from trajectory_gym.env import tools
from trajectory_gym.env.database import connect, reset_from_dump
from trajectory_gym.env.state import EpisodeState


def _fresh_state(scenario_id: str) -> EpisodeState:
    conn = connect(":memory:")
    reset_from_dump(conn)
    return EpisodeState(conn=conn, scenario_id=scenario_id)


def test_injection_roll_is_pure_function_of_the_seed_tuple():
    a = tools._injection_roll("SCEN_A", "lookup_order", 3)
    b = tools._injection_roll("SCEN_A", "lookup_order", 3)
    c = tools._injection_roll("SCEN_A", "lookup_order", 4)
    d = tools._injection_roll("SCEN_B", "lookup_order", 3)
    assert a == b
    assert a != c
    assert a != d


def test_lookup_order_stale_pattern_is_reproducible_across_episodes():
    def stale_flags(scenario_id: str, n: int) -> list[bool]:
        state = _fresh_state(scenario_id)
        flags = []
        for _ in range(n):
            result = tools.lookup_order(state, "O0001")
            flags.append(bool(result.get("_stale")))
        return flags

    run_1 = stale_flags("REPRO_SCENARIO", 40)
    run_2 = stale_flags("REPRO_SCENARIO", 40)
    assert run_1 == run_2
    # with a 10% rate over 40 calls, expect at least one stale and not all stale
    assert any(run_1)
    assert not all(run_1)


def test_lookup_customer_timeout_pattern_is_reproducible_across_episodes():
    def timeout_flags(scenario_id: str, n: int) -> list[bool]:
        state = _fresh_state(scenario_id)
        flags = []
        for _ in range(n):
            result = tools.lookup_customer(state, customer_id="C0001")
            flags.append(result.get("error") == "TIMEOUT")
        return flags

    run_1 = timeout_flags("REPRO_SCENARIO_2", 40)
    run_2 = timeout_flags("REPRO_SCENARIO_2", 40)
    assert run_1 == run_2
    assert any(run_1)
    assert not all(run_1)


def test_stale_status_differs_from_true_status_when_injected(db):
    state = EpisodeState(conn=db, scenario_id="REPRO_SCENARIO")
    true_status = db.execute("SELECT status FROM orders WHERE id = 'O0001'").fetchone()[0]
    # index 0 for REPRO_SCENARIO/lookup_order was asserted stale by the test above's fixed seed
    result = tools.lookup_order(state, "O0001")
    if result.get("_stale"):
        assert result["status"] != true_status
    else:
        assert result["status"] == true_status


def test_force_stale_status_overrides_the_roll_on_first_call(db):
    state = EpisodeState(conn=db, scenario_id="ANY_SCENARIO", force_stale_status=True)
    true_status = db.execute("SELECT status FROM orders WHERE id = 'O0001'").fetchone()[0]
    result = tools.lookup_order(state, "O0001")
    assert result["_stale"] is True
    assert result["status"] != true_status
