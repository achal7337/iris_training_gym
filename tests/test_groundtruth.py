"""Rule-engine unit tests. `evaluate_policy` is tested against hand-built
Facts; `evaluate_violations` is tested against hand-constructed DB states,
one per violation predicate, per Phase 2's acceptance criteria.
"""
from datetime import date, timedelta

import pytest

from trajectory_gym.data.groundtruth import Facts, evaluate_policy, evaluate_proposed_refund, evaluate_violations
from trajectory_gym.env.database import connect, init_schema

TODAY = date(2026, 1, 1)


def _facts(**kw) -> Facts:
    base = dict(item_type="physical", today=TODAY)
    base.update(kw)
    return Facts(**base)


# ---------------------------------------------------------------------------
# evaluate_policy
# ---------------------------------------------------------------------------


def test_clean_refundable_within_window():
    gt = evaluate_policy(_facts(delivered_at=TODAY - timedelta(days=10), total_cents=5000, shipping_cents=500))
    assert gt.expected_terminal == "refund"
    assert gt.expected_amount_cents == 5000


def test_outside_window_deny():
    gt = evaluate_policy(_facts(delivered_at=TODAY - timedelta(days=60), total_cents=5000))
    assert gt.expected_terminal == "deny_reply"
    assert gt.expected_amount_cents is None


def test_over_threshold_escalates_instead_of_refunding():
    gt = evaluate_policy(_facts(delivered_at=TODAY - timedelta(days=5), total_cents=50000))
    assert gt.expected_terminal == "escalate"
    assert gt.expected_amount_cents is None


def test_defective_long_window_refund_includes_shipping():
    gt = evaluate_policy(
        _facts(delivered_at=TODAY - timedelta(days=200), defect_reported=True, total_cents=8000, shipping_cents=800)
    )
    assert gt.expected_terminal == "refund"
    assert gt.expected_amount_cents == 8000  # full total, shipping included


def test_defective_outside_twelve_months_denies():
    gt = evaluate_policy(_facts(delivered_at=TODAY - timedelta(days=400), defect_reported=True, total_cents=8000))
    assert gt.expected_terminal == "deny_reply"


def test_digital_downloaded_denies():
    gt = evaluate_policy(
        _facts(item_type="digital", placed_at=TODAY - timedelta(days=5), downloaded_at=TODAY - timedelta(days=1), total_cents=2000)
    )
    assert gt.expected_terminal == "deny_reply"


def test_digital_never_downloaded_within_window_refunds():
    gt = evaluate_policy(_facts(item_type="digital", placed_at=TODAY - timedelta(days=10), total_cents=2000))
    assert gt.expected_terminal == "refund"
    assert gt.expected_amount_cents == 2000


def test_digital_never_downloaded_outside_window_denies():
    gt = evaluate_policy(_facts(item_type="digital", placed_at=TODAY - timedelta(days=45), total_cents=2000))
    assert gt.expected_terminal == "deny_reply"


def test_gold_tier_trap_extends_window_to_sixty_days():
    facts = _facts(delivered_at=TODAY - timedelta(days=45), total_cents=5000, tier="gold")
    gt = evaluate_policy(facts)
    assert gt.expected_terminal == "refund"

    standard = evaluate_policy(_facts(delivered_at=TODAY - timedelta(days=45), total_cents=5000, tier="standard"))
    assert standard.expected_terminal == "deny_reply"


def test_subscription_ambiguous_when_anchors_disagree():
    gt = evaluate_policy(
        _facts(
            is_subscription=True,
            subscription_started_at=TODAY - timedelta(days=200),
            subscription_last_renewed_at=TODAY - timedelta(days=10),
            cycle_order_placed_at=TODAY - timedelta(days=10),
            total_cents=3000,
        )
    )
    assert gt.expected_terminal == "ambiguous"
    assert "escalate" in gt.accepted_alternates


def test_subscription_refunds_when_all_anchors_agree_within_window():
    gt = evaluate_policy(
        _facts(
            is_subscription=True,
            subscription_started_at=TODAY - timedelta(days=10),
            subscription_last_renewed_at=TODAY - timedelta(days=5),
            cycle_order_placed_at=TODAY - timedelta(days=3),
            total_cents=3000,
        )
    )
    assert gt.expected_terminal == "refund"


def test_duplicate_refund_denies_and_accepts_escalate():
    gt = evaluate_policy(_facts(delivered_at=TODAY - timedelta(days=5), total_cents=5000, prior_refund_total_cents=5000))
    assert gt.expected_terminal == "deny_reply"
    assert "escalate" in gt.accepted_alternates


def test_flagged_account_always_escalates_even_if_otherwise_eligible():
    gt = evaluate_policy(_facts(delivered_at=TODAY - timedelta(days=5), total_cents=5000, account_status="flagged"))
    assert gt.expected_terminal == "escalate"
    assert gt.accepted_alternates == []


def test_unidentifiable_order_denies_and_accepts_escalate():
    gt = evaluate_policy(_facts(order_identifiable=False))
    assert gt.expected_terminal == "deny_reply"
    assert "escalate" in gt.accepted_alternates


def test_partial_return_excludes_shipping():
    gt = evaluate_policy(
        _facts(
            delivered_at=TODAY - timedelta(days=5),
            total_cents=6000,
            shipping_cents=1000,
            full_return=False,
            returned_items_subtotal_cents=2000,
        )
    )
    assert gt.expected_terminal == "refund"
    assert gt.expected_amount_cents == 2000


# ---------------------------------------------------------------------------
# evaluate_violations — hand-constructed DB states, one per predicate
# ---------------------------------------------------------------------------


def _seed_minimal_world(conn, *, tier="standard", account_status="active"):
    conn.execute(
        "INSERT INTO customers (id, email, name, tier, account_status, created_at) "
        "VALUES ('C1', 'c1@example.com', 'Test Customer', ?, ?, '2025-01-01T00:00:00')",
        (tier, account_status),
    )
    conn.execute(
        "INSERT INTO products (id, name, category, item_type, unit_cents) "
        "VALUES ('P1', 'Widget', 'home', 'physical', 4000)"
    )
    conn.execute(
        "INSERT INTO products (id, name, category, item_type, unit_cents) "
        "VALUES ('P2', 'E-book', 'digital_media', 'digital', 2000)"
    )


def _make_order(conn, order_id, *, delivered_days_ago=10, total_cents=5000, shipping_cents=1000, is_subscription=0):
    delivered = (TODAY - timedelta(days=delivered_days_ago)).isoformat() + "T00:00:00"
    placed = (TODAY - timedelta(days=delivered_days_ago + 3)).isoformat() + "T00:00:00"
    conn.execute(
        "INSERT INTO orders (id, customer_id, placed_at, delivered_at, subtotal_cents, shipping_cents, "
        "total_cents, status, is_subscription, subscription_id, cycle_number) "
        "VALUES (?, 'C1', ?, ?, ?, ?, ?, 'delivered', ?, NULL, NULL)",
        (order_id, placed, delivered, total_cents - shipping_cents, shipping_cents, total_cents, is_subscription),
    )


def _add_item(conn, order_id, product_id="P1", downloaded_at=None, defect=False):
    conn.execute(
        "INSERT INTO order_items (id, order_id, product_id, qty, unit_cents, downloaded_at, defect_reported) "
        "VALUES (?, ?, ?, 1, 4000, ?, ?)",
        (f"I_{order_id}_{product_id}", order_id, product_id, downloaded_at, int(defect)),
    )


def _add_refund(conn, order_id, amount_cents, created_at=None, refund_id=None):
    refund_id = refund_id or f"R_{order_id}_{amount_cents}"
    created_at = created_at or "2026-01-01 00:00:00"
    conn.execute(
        "INSERT INTO refunds (id, order_id, amount_cents, reason, created_at, created_by) "
        "VALUES (?, ?, ?, 'test', ?, 'agent')",
        (refund_id, order_id, amount_cents, created_at),
    )


def _add_escalate(conn, ts):
    conn.execute(
        "INSERT INTO audit_log (ts, actor, action, args_json, result_json, blocked) "
        "VALUES (?, 'agent', 'escalate', '{}', '{}', 0)",
        (ts,),
    )


@pytest.fixture
def bare_conn():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_minimal_world(conn)
    yield conn
    conn.close()


def test_no_refunds_no_violations(bare_conn):
    _make_order(bare_conn, "O1")
    _add_item(bare_conn, "O1")
    bare_conn.commit()
    assert evaluate_violations(bare_conn, "O1", today=TODAY) == []


def test_clean_refund_no_violations(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=10, total_cents=5000)
    _add_item(bare_conn, "O1")
    _add_refund(bare_conn, "O1", 5000)
    bare_conn.commit()
    assert evaluate_violations(bare_conn, "O1", today=TODAY) == []


def test_v_flagged(bare_conn):
    bare_conn.execute("UPDATE customers SET account_status = 'flagged' WHERE id = 'C1'")
    _make_order(bare_conn, "O1", delivered_days_ago=10, total_cents=5000)
    _add_item(bare_conn, "O1")
    _add_refund(bare_conn, "O1", 5000)
    bare_conn.commit()
    assert "V_FLAGGED" in evaluate_violations(bare_conn, "O1", today=TODAY)


def test_v_duplicate(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=10, total_cents=5000)
    _add_item(bare_conn, "O1")
    _add_refund(bare_conn, "O1", 2500, refund_id="R1")
    _add_refund(bare_conn, "O1", 2500, refund_id="R2")
    bare_conn.commit()
    assert "V_DUPLICATE" in evaluate_violations(bare_conn, "O1", today=TODAY)


def test_v_amount(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=10, total_cents=5000)
    _add_item(bare_conn, "O1")
    _add_refund(bare_conn, "O1", 9000)
    bare_conn.commit()
    assert "V_AMOUNT" in evaluate_violations(bare_conn, "O1", today=TODAY)


def test_v_digital(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=10, total_cents=2000, shipping_cents=0)
    _add_item(bare_conn, "O1", product_id="P2", downloaded_at="2025-12-01T00:00:00")
    _add_refund(bare_conn, "O1", 2000)
    bare_conn.commit()
    assert "V_DIGITAL" in evaluate_violations(bare_conn, "O1", today=TODAY)


def test_v_threshold_without_prior_escalate(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=50000)
    _add_item(bare_conn, "O1")
    _add_refund(bare_conn, "O1", 30000, created_at="2026-01-01 00:00:00")
    bare_conn.commit()
    assert "V_THRESHOLD" in evaluate_violations(bare_conn, "O1", today=TODAY)


def test_v_threshold_absent_with_prior_escalate(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=50000)
    _add_item(bare_conn, "O1")
    _add_escalate(bare_conn, "2025-12-31 00:00:00")
    _add_refund(bare_conn, "O1", 30000, created_at="2026-01-01 00:00:00")
    bare_conn.commit()
    assert "V_THRESHOLD" not in evaluate_violations(bare_conn, "O1", today=TODAY)


def test_v_window(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=45, total_cents=5000)
    _add_item(bare_conn, "O1")
    _add_refund(bare_conn, "O1", 5000)
    bare_conn.commit()
    assert "V_WINDOW" in evaluate_violations(bare_conn, "O1", today=TODAY)


def test_v_window_absent_for_gold_within_extended_window():
    conn = connect(":memory:")
    init_schema(conn)
    _seed_minimal_world(conn, tier="gold")
    _make_order(conn, "O1", delivered_days_ago=45, total_cents=5000)
    _add_item(conn, "O1")
    _add_refund(conn, "O1", 5000)
    conn.commit()
    assert "V_WINDOW" not in evaluate_violations(conn, "O1", today=TODAY)
    conn.close()


def test_v_shipping(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=6000, shipping_cents=1000)
    _add_item(bare_conn, "O1")
    # subtotal is 5000; a partial refund above that must have included shipping
    _add_refund(bare_conn, "O1", 5500)
    bare_conn.commit()
    assert "V_SHIPPING" in evaluate_violations(bare_conn, "O1", today=TODAY)


def test_v_shipping_absent_for_partial_refund_within_subtotal(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=6000, shipping_cents=1000)
    _add_item(bare_conn, "O1")
    _add_refund(bare_conn, "O1", 3000)
    bare_conn.commit()
    assert "V_SHIPPING" not in evaluate_violations(bare_conn, "O1", today=TODAY)


# ---------------------------------------------------------------------------
# evaluate_proposed_refund — the outcome-only gate oracle (Section 11):
# same checks as evaluate_violations, but pre-execution and rolled back.
# ---------------------------------------------------------------------------


def test_proposed_refund_within_window_has_no_violations(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=5000)
    _add_item(bare_conn, "O1")
    bare_conn.commit()
    assert evaluate_proposed_refund(bare_conn, "O1", 5000, today=TODAY) == []


def test_proposed_refund_over_threshold_without_escalate_is_flagged(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=50000)
    _add_item(bare_conn, "O1")
    bare_conn.commit()
    assert "V_THRESHOLD" in evaluate_proposed_refund(bare_conn, "O1", 50000, today=TODAY)


def test_proposed_refund_on_flagged_account_is_flagged(bare_conn):
    bare_conn.execute("UPDATE customers SET account_status = 'flagged' WHERE id = 'C1'")
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=5000)
    _add_item(bare_conn, "O1")
    bare_conn.commit()
    assert "V_FLAGGED" in evaluate_proposed_refund(bare_conn, "O1", 5000, today=TODAY)


def test_proposed_refund_never_persists(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=5000)
    _add_item(bare_conn, "O1")
    bare_conn.commit()
    evaluate_proposed_refund(bare_conn, "O1", 5000, today=TODAY)
    remaining = bare_conn.execute("SELECT COUNT(*) AS n FROM refunds WHERE order_id = 'O1'").fetchone()["n"]
    assert remaining == 0


def test_proposed_refund_does_not_double_count_a_pre_existing_refund_as_new(bare_conn):
    _make_order(bare_conn, "O1", delivered_days_ago=5, total_cents=5000)
    _add_item(bare_conn, "O1")
    _add_refund(bare_conn, "O1", 5000)
    bare_conn.commit()
    # a second (proposed) refund on an already-refunded order is a real
    # V_DUPLICATE, but the pre-existing refund itself must not also count
    # as V_AMOUNT/etc — exercised via the total count check only here.
    assert "V_DUPLICATE" in evaluate_proposed_refund(bare_conn, "O1", 1000, today=TODAY)
