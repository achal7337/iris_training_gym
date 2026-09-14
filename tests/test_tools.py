import pytest

from trajectory_gym.env import tools
from trajectory_gym.env.state import EpisodeState


def test_lookup_order_found(state):
    result = tools.lookup_order(state, "O0001")
    assert result["id"] == "O0001"
    assert "items" in result and len(result["items"]) >= 1


def test_lookup_order_not_found(state):
    result = tools.lookup_order(state, "O9999")
    assert result["error"] == "NOT_FOUND"


def test_lookup_customer_by_id(state):
    result = tools.lookup_customer(state, customer_id="C0001")
    assert result["id"] == "C0001"
    assert "orders" in result
    assert all({"order_id", "placed_at", "total_cents"} <= o.keys() for o in result["orders"])


def test_lookup_customer_by_email(state, db):
    email = db.execute("SELECT email FROM customers WHERE id = 'C0001'").fetchone()[0]
    result = tools.lookup_customer(state, email=email)
    assert result["id"] == "C0001"


def test_lookup_customer_requires_identifier(state):
    with pytest.raises(tools.ToolError):
        tools.lookup_customer(state)


def test_read_policy_returns_top_k(state):
    result = tools.read_policy(state, "refund window eligibility")
    assert len(result["chunks"]) == 2
    for chunk in result["chunks"]:
        assert chunk["header"].startswith("## Section")


def test_read_policy_retrieval_trap_hides_gold_rule_for_generic_query(state):
    result = tools.read_policy(state, "refund window eligibility")
    headers = " ".join(c["header"] for c in result["chunks"])
    assert "Loyalty" not in headers


def test_read_policy_surfaces_gold_rule_for_tier_query(state):
    result = tools.read_policy(state, "gold member tier return window")
    headers = " ".join(c["header"] for c in result["chunks"])
    assert "Loyalty" in headers


def test_inspect_refund_history_empty_then_populated(state):
    assert tools.inspect_refund_history(state, "O0001")["refunds"] == []
    tools.issue_refund(state, "O0001", 100, "test")
    history = tools.inspect_refund_history(state, "O0001")["refunds"]
    assert len(history) == 1
    assert history[0]["amount_cents"] == 100


def test_issue_refund_rejects_amount_over_total(state, db):
    total = db.execute("SELECT total_cents FROM orders WHERE id = 'O0001'").fetchone()[0]
    result = tools.issue_refund(state, "O0001", total + 1, "too much")
    assert result["error"] == "AMOUNT_EXCEEDS_ORDER_TOTAL"
    assert db.execute("SELECT COUNT(*) FROM refunds WHERE order_id = 'O0001'").fetchone()[0] == 0


def test_issue_refund_not_found(state):
    result = tools.issue_refund(state, "O9999", 100, "x")
    assert result["error"] == "NOT_FOUND"


def test_issue_refund_succeeds_and_is_appended(state, db):
    result = tools.issue_refund(state, "O0001", 100, "test")
    assert "refund_id" in result
    result2 = tools.issue_refund(state, "O0001", 50, "second")
    assert result2["refund_id"] != result["refund_id"]
    assert db.execute("SELECT COUNT(*) FROM refunds WHERE order_id = 'O0001'").fetchone()[0] == 2


def test_escalate_and_reply_ack(state):
    assert tools.escalate(state, "need help")["ack"] is True
    assert tools.reply_and_close(state, "done")["ack"] is True


def test_every_tool_call_appends_audit_log(state, db):
    before = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    tools.lookup_order(state, "O0001")
    after = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert after == before + 1


def test_call_tool_dispatch(state):
    result = tools.call_tool(state, "lookup_order", {"order_id": "O0001"})
    assert result["id"] == "O0001"


def test_call_tool_unknown_raises(state):
    with pytest.raises(tools.ToolError):
        tools.call_tool(state, "delete_everything", {})


def test_only_seven_tools_registered():
    assert set(tools.TOOLS.keys()) == {
        "lookup_order",
        "lookup_customer",
        "read_policy",
        "inspect_refund_history",
        "issue_refund",
        "escalate",
        "reply_and_close",
    }
