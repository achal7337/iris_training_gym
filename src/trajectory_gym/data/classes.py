"""The ten scenario class templates — Section 6 of prompt.md.

Generation is ground-truth-first: sample facts under constraints that
guarantee the class, then call `evaluate_policy` (the rule engine) on those
facts to derive ground truth. Nothing here hardcodes a class's ground truth
directly — it falls out of the same policy logic that later scores runs.

Each sampler returns a `Draw`: the facts, the (sql, params) fixture that
instantiates those facts on top of the reset base world, and hints for the
prose writer describing only what the *customer* would plausibly say (never
the policy reasoning — see docs/reward_design.md and Section 6's leak
blocklist).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import timedelta

from .groundtruth import ANCHOR, Facts
from .world import N_CUSTOMERS

SEED = 42
N_PER_CLASS = 5

# Fixed class ordering used only to compute globally-unique, ordinary-looking
# IDs (O0181, O0182, ... continuing the base world's O0001-O0180) for
# scenario orders/subscriptions. A visually distinct ID scheme (e.g.
# "OS-C3-1") turned out to bias the agent — a weak model would ignore an
# odd-looking ID in a lookup_customer result and fixate on the normal-looking
# ones, which has nothing to do with policy reasoning and would have silently
# confounded every scenario the same way.
CLASS_ORDER = [
    "clean_refundable", "outside_window_deny", "over_threshold_escalate", "defective_long_window",
    "digital_downloaded", "gold_tier_trap", "subscription_ambiguity", "duplicate_refund",
    "flagged_account", "missing_or_wrong_id",
]
_BASE_ORDER_NUMBER = 181  # base world uses O0001-O0180
_BASE_DECOY_NUMBER = _BASE_ORDER_NUMBER + len(CLASS_ORDER) * N_PER_CLASS  # 231+
_BASE_SUBSCRIPTION_NUMBER = 21  # base world uses S01-S20

PHYSICAL_PRODUCT_IDS = [f"P{i:02d}" for i in range(1, 18)]
DIGITAL_PRODUCT_IDS = [f"P{i:02d}" for i in range(18, 26)]


def _rng(scenario_class: str, index: int) -> random.Random:
    return random.Random(f"{SEED}|{scenario_class}|{index}")


def _iso(d) -> str:
    return f"{d.isoformat()}T00:00:00"


def _pick_customer(rng: random.Random) -> str:
    return f"C{rng.randint(1, N_CUSTOMERS):04d}"


SqlOp = tuple[str, list]


def _insert_order(
    order_id: str, customer_id: str, placed_at: str, delivered_at: str | None,
    subtotal_cents: int, shipping_cents: int, total_cents: int, status: str,
    is_subscription: int = 0, subscription_id: str | None = None, cycle_number: int | None = None,
) -> SqlOp:
    return (
        "INSERT INTO orders (id, customer_id, placed_at, delivered_at, subtotal_cents, "
        "shipping_cents, total_cents, status, is_subscription, subscription_id, cycle_number) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [order_id, customer_id, placed_at, delivered_at, subtotal_cents, shipping_cents,
         total_cents, status, is_subscription, subscription_id, cycle_number],
    )


def _insert_item(
    item_id: str, order_id: str, product_id: str, qty: int, unit_cents: int,
    downloaded_at: str | None = None, defect: bool = False,
) -> SqlOp:
    return (
        "INSERT INTO order_items (id, order_id, product_id, qty, unit_cents, downloaded_at, defect_reported) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [item_id, order_id, product_id, qty, unit_cents, downloaded_at, int(defect)],
    )


def _update_customer(customer_id: str, tier: str, account_status: str) -> SqlOp:
    return (
        "UPDATE customers SET tier = ?, account_status = ? WHERE id = ?",
        [tier, account_status, customer_id],
    )


def _insert_subscription(sub_id: str, customer_id: str, started_at: str, last_renewed_at: str) -> SqlOp:
    return (
        "INSERT INTO subscriptions (id, customer_id, started_at, last_renewed_at, status) "
        "VALUES (?, ?, ?, ?, 'active')",
        [sub_id, customer_id, started_at, last_renewed_at],
    )


def _insert_refund(refund_id: str, order_id: str, amount_cents: int, reason: str, created_at: str) -> SqlOp:
    return (
        "INSERT INTO refunds (id, order_id, amount_cents, reason, created_at, created_by) "
        "VALUES (?, ?, ?, ?, ?, 'agent')",
        [refund_id, order_id, amount_cents, reason, created_at],
    )


@dataclass
class Draw:
    scenario_class: str
    index: int
    customer_id: str
    order_id: str
    facts: Facts
    setup_sql: list[SqlOp] = field(default_factory=list)
    ticket_hints: list[str] = field(default_factory=list)
    force_stale_status: bool = False


def _oid(scenario_class: str, index: int) -> str:
    n = _BASE_ORDER_NUMBER + CLASS_ORDER.index(scenario_class) * N_PER_CLASS + (index - 1)
    return f"O{n:04d}"


def _decoy_oid(index: int, d: int) -> str:
    # only called for missing_or_wrong_id's unresolvable indices (4, 5), 2 decoys each
    n = _BASE_DECOY_NUMBER + (index - 4) * 2 + d
    return f"O{n:04d}"


def _sub_id(index: int) -> str:
    return f"S{_BASE_SUBSCRIPTION_NUMBER + index - 1:02d}"


# ---------------------------------------------------------------------------
# C1 — clean_refundable
# ---------------------------------------------------------------------------

def _sample_c1(index: int) -> Draw:
    rng = _rng("clean_refundable", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("clean_refundable", index)
    delivered_days_ago = rng.randint(2, 25)
    placed_days_ago = delivered_days_ago + rng.randint(1, 5)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    shipping_cents = rng.randint(300, 1200)
    is_partial = index in (4, 5)

    setup = [_update_customer(customer_id, "standard", "active")]

    if not is_partial:
        total_cents = rng.randint(2000, 18000)
        subtotal_cents = total_cents - shipping_cents
        product_id = rng.choice(PHYSICAL_PRODUCT_IDS)
        setup.append(_insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                                    subtotal_cents, shipping_cents, total_cents, "delivered"))
        setup.append(_insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents))
        facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                       shipping_cents=shipping_cents, full_return=True)
        hints = []
    else:
        unit_a = rng.randint(800, 4000)
        unit_b = rng.randint(800, 4000)
        unit_c = rng.randint(800, 4000)
        subtotal_cents = unit_a + unit_b + unit_c
        total_cents = subtotal_cents + shipping_cents
        products = rng.sample(PHYSICAL_PRODUCT_IDS, 3)
        setup.append(_insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                                    subtotal_cents, shipping_cents, total_cents, "delivered"))
        for i, (pid, unit) in enumerate(zip(products, [unit_a, unit_b, unit_c]), start=1):
            setup.append(_insert_item(f"{order_id}-I{i}", order_id, pid, 1, unit))
        facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                       shipping_cents=shipping_cents, full_return=False,
                       returned_items_subtotal_cents=unit_a)
        hints = [
            "The customer is returning only one of the three items from this order and is "
            "asking for a refund for just that item, not the whole order."
        ]

    return Draw("clean_refundable", index, customer_id, order_id, facts, setup, hints)


# ---------------------------------------------------------------------------
# C2 — outside_window_deny
# ---------------------------------------------------------------------------

def _sample_c2(index: int) -> Draw:
    rng = _rng("outside_window_deny", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("outside_window_deny", index)
    delivered_days_ago = rng.randint(35, 90)
    placed_days_ago = delivered_days_ago + rng.randint(1, 5)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    shipping_cents = rng.randint(300, 1200)
    total_cents = rng.randint(2000, 19900)
    subtotal_cents = total_cents - shipping_cents
    product_id = rng.choice(PHYSICAL_PRODUCT_IDS)

    setup = [
        _update_customer(customer_id, "standard", "active"),
        _insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                       subtotal_cents, shipping_cents, total_cents, "delivered"),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents),
    ]
    facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                   shipping_cents=shipping_cents, full_return=True)
    return Draw("outside_window_deny", index, customer_id, order_id, facts, setup, [])


# ---------------------------------------------------------------------------
# C3 — over_threshold_escalate
# ---------------------------------------------------------------------------

def _sample_c3(index: int) -> Draw:
    rng = _rng("over_threshold_escalate", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("over_threshold_escalate", index)
    delivered_days_ago = rng.randint(2, 25)
    placed_days_ago = delivered_days_ago + rng.randint(1, 5)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    shipping_cents = rng.randint(500, 2000)
    total_cents = rng.randint(20500, 90000)
    subtotal_cents = total_cents - shipping_cents
    product_id = rng.choice(PHYSICAL_PRODUCT_IDS)

    setup = [
        _update_customer(customer_id, "standard", "active"),
        _insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                       subtotal_cents, shipping_cents, total_cents, "delivered"),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents),
    ]
    facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                   shipping_cents=shipping_cents, full_return=True)
    return Draw("over_threshold_escalate", index, customer_id, order_id, facts, setup, [])


# ---------------------------------------------------------------------------
# C4 — defective_long_window
# ---------------------------------------------------------------------------

def _sample_c4(index: int) -> Draw:
    rng = _rng("defective_long_window", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("defective_long_window", index)
    delivered_days_ago = rng.randint(40, 300)
    placed_days_ago = delivered_days_ago + rng.randint(1, 5)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    shipping_cents = rng.randint(300, 1200)
    total_cents = rng.randint(2000, 19900)
    subtotal_cents = total_cents - shipping_cents
    product_id = rng.choice(PHYSICAL_PRODUCT_IDS)

    setup = [
        _update_customer(customer_id, "standard", "active"),
        _insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                       subtotal_cents, shipping_cents, total_cents, "delivered"),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents, defect=True),
    ]
    facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                   shipping_cents=shipping_cents, defect_reported=True, full_return=True)
    hints = ["The customer reports that the item arrived defective / stopped working, and describes the defect."]
    return Draw("defective_long_window", index, customer_id, order_id, facts, setup, hints)


# ---------------------------------------------------------------------------
# C5 — digital_downloaded
# ---------------------------------------------------------------------------

def _sample_c5(index: int) -> Draw:
    rng = _rng("digital_downloaded", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("digital_downloaded", index)
    placed_days_ago = rng.randint(1, 20)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    total_cents = rng.randint(500, 15000)
    product_id = rng.choice(DIGITAL_PRODUCT_IDS)
    is_downloaded = index != 5  # 4 of 5 downloaded -> deny; 1 of 5 not -> refund

    downloaded_at = None
    if is_downloaded:
        downloaded_days_ago = rng.randint(0, max(0, placed_days_ago - 1))
        downloaded_at = _iso(ANCHOR - timedelta(days=downloaded_days_ago))

    setup = [
        _update_customer(customer_id, "standard", "active"),
        _insert_order(order_id, customer_id, _iso(placed_at), _iso(placed_at),
                       total_cents, 0, total_cents, "delivered"),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, total_cents, downloaded_at=downloaded_at),
    ]
    facts = Facts(item_type="digital", placed_at=placed_at, total_cents=total_cents,
                   shipping_cents=0, downloaded_at=(ANCHOR - timedelta(days=downloaded_days_ago)) if is_downloaded else None)
    hints = ["The customer bought a digital product." + (" They mention they already downloaded/accessed it." if is_downloaded else " They mention they have not downloaded or accessed it yet.")]
    return Draw("digital_downloaded", index, customer_id, order_id, facts, setup, hints)


# ---------------------------------------------------------------------------
# C6 — gold_tier_trap
# ---------------------------------------------------------------------------

def _sample_c6(index: int) -> Draw:
    rng = _rng("gold_tier_trap", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("gold_tier_trap", index)
    delivered_days_ago = rng.randint(31, 58)
    placed_days_ago = delivered_days_ago + rng.randint(1, 5)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    shipping_cents = rng.randint(300, 1200)
    total_cents = rng.randint(2000, 19900)
    subtotal_cents = total_cents - shipping_cents
    product_id = rng.choice(PHYSICAL_PRODUCT_IDS)

    setup = [
        _update_customer(customer_id, "gold", "active"),
        _insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                       subtotal_cents, shipping_cents, total_cents, "delivered"),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents),
    ]
    facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                   shipping_cents=shipping_cents, tier="gold", full_return=True)
    return Draw("gold_tier_trap", index, customer_id, order_id, facts, setup, [])


# ---------------------------------------------------------------------------
# C7 — subscription_ambiguity
# ---------------------------------------------------------------------------

def _sample_c7(index: int) -> Draw:
    rng = _rng("subscription_ambiguity", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("subscription_ambiguity", index)
    sub_id = _sub_id(index)

    started_days_ago = rng.randint(120, 400)
    renewed_days_ago = rng.randint(5, 25)
    cycle_placed_days_ago = rng.randint(5, 25)
    delivered_days_ago = min(rng.randint(2, 20), max(1, cycle_placed_days_ago - 1))

    started_at = ANCHOR - timedelta(days=started_days_ago)
    renewed_at = ANCHOR - timedelta(days=renewed_days_ago)
    cycle_placed_at = ANCHOR - timedelta(days=cycle_placed_days_ago)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)

    shipping_cents = rng.randint(0, 800)
    total_cents = rng.randint(1500, 19000)
    subtotal_cents = total_cents - shipping_cents
    product_id = rng.choice(PHYSICAL_PRODUCT_IDS)

    setup = [
        _update_customer(customer_id, "standard", "active"),
        _insert_subscription(sub_id, customer_id, _iso(started_at), _iso(renewed_at)),
        _insert_order(order_id, customer_id, _iso(cycle_placed_at), _iso(delivered_at),
                       subtotal_cents, shipping_cents, total_cents, "delivered",
                       is_subscription=1, subscription_id=sub_id, cycle_number=1),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents),
    ]
    facts = Facts(item_type="physical", is_subscription=True, total_cents=total_cents,
                   shipping_cents=shipping_cents,
                   subscription_started_at=started_at, subscription_last_renewed_at=renewed_at,
                   cycle_order_placed_at=cycle_placed_at, delivered_at=delivered_at)
    hints = ["The customer has a recurring subscription order and is asking for a refund on a recent charge."]
    return Draw("subscription_ambiguity", index, customer_id, order_id, facts, setup, hints)


# ---------------------------------------------------------------------------
# C8 — duplicate_refund
# ---------------------------------------------------------------------------

def _sample_c8(index: int) -> Draw:
    rng = _rng("duplicate_refund", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("duplicate_refund", index)
    delivered_days_ago = rng.randint(2, 25)
    placed_days_ago = delivered_days_ago + rng.randint(1, 5)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    shipping_cents = rng.randint(300, 1200)
    total_cents = rng.randint(2000, 18000)
    subtotal_cents = total_cents - shipping_cents
    product_id = rng.choice(PHYSICAL_PRODUCT_IDS)
    prior_refund_at = _iso(ANCHOR - timedelta(days=max(0, delivered_days_ago - 1)))

    setup = [
        _update_customer(customer_id, "standard", "active"),
        _insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                       subtotal_cents, shipping_cents, total_cents, "delivered"),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents),
        _insert_refund(f"{order_id}-R1", order_id, total_cents, "customer requested refund", prior_refund_at),
    ]
    facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                   shipping_cents=shipping_cents, prior_refund_total_cents=total_cents, full_return=True)
    hints = ["This is a follow-up message from the customer asking again about a refund for this order."]
    return Draw("duplicate_refund", index, customer_id, order_id, facts, setup, hints)


# ---------------------------------------------------------------------------
# C9 — flagged_account
# ---------------------------------------------------------------------------

def _sample_c9(index: int) -> Draw:
    rng = _rng("flagged_account", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("flagged_account", index)
    delivered_days_ago = rng.randint(2, 25)
    placed_days_ago = delivered_days_ago + rng.randint(1, 5)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    shipping_cents = rng.randint(300, 1200)
    total_cents = rng.randint(2000, 18000)
    subtotal_cents = total_cents - shipping_cents
    product_id = rng.choice(PHYSICAL_PRODUCT_IDS)

    setup = [
        _update_customer(customer_id, "standard", "flagged"),
        _insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                       subtotal_cents, shipping_cents, total_cents, "delivered"),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents),
    ]
    facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                   shipping_cents=shipping_cents, account_status="flagged", full_return=True)
    return Draw("flagged_account", index, customer_id, order_id, facts, setup, [])


# ---------------------------------------------------------------------------
# C10 — missing_or_wrong_id
# ---------------------------------------------------------------------------

def _sample_c10(index: int) -> Draw:
    rng = _rng("missing_or_wrong_id", index)
    customer_id = _pick_customer(rng)
    order_id = _oid("missing_or_wrong_id", index)
    is_resolvable = index in (1, 2, 3)

    delivered_days_ago = rng.randint(2, 25)
    placed_days_ago = delivered_days_ago + rng.randint(1, 5)
    delivered_at = ANCHOR - timedelta(days=delivered_days_ago)
    placed_at = ANCHOR - timedelta(days=placed_days_ago)
    shipping_cents = rng.randint(300, 1200)
    total_cents = rng.randint(2000, 18000)
    subtotal_cents = total_cents - shipping_cents
    product_id = rng.choice(PHYSICAL_PRODUCT_IDS)

    setup = [
        _update_customer(customer_id, "standard", "active"),
        _insert_order(order_id, customer_id, _iso(placed_at), _iso(delivered_at),
                       subtotal_cents, shipping_cents, total_cents, "delivered"),
        _insert_item(f"{order_id}-I1", order_id, product_id, 1, subtotal_cents),
    ]

    if is_resolvable:
        facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                       shipping_cents=shipping_cents, order_identifiable=True, full_return=True)
        hints = [
            "The customer does not give an order number. They describe the order in general "
            "terms and expect support to look it up using their account email."
        ]
    else:
        # 2-3 similar decoy orders for the same customer make this genuinely unresolvable.
        for d in range(2):
            decoy_id = _decoy_oid(index, d)
            decoy_delivered_days_ago = delivered_days_ago + rng.randint(-3, 3)
            decoy_delivered_at = ANCHOR - timedelta(days=max(1, decoy_delivered_days_ago))
            decoy_placed_at = decoy_delivered_at - timedelta(days=rng.randint(1, 5))
            decoy_total = total_cents + rng.randint(-500, 500)
            decoy_product = rng.choice(PHYSICAL_PRODUCT_IDS)
            setup.append(_insert_order(decoy_id, customer_id, _iso(decoy_placed_at), _iso(decoy_delivered_at),
                                        decoy_total - shipping_cents, shipping_cents, decoy_total, "delivered"))
            setup.append(_insert_item(f"{decoy_id}-I1", decoy_id, decoy_product, 1, decoy_total - shipping_cents))
        facts = Facts(item_type="physical", delivered_at=delivered_at, total_cents=total_cents,
                       shipping_cents=shipping_cents, order_identifiable=False, full_return=True)
        hints = [
            "The customer is vague about which order this concerns and mentions they've placed "
            "several similar orders recently. They do not give a specific, correct order number."
        ]

    return Draw("missing_or_wrong_id", index, customer_id, order_id, facts, setup, hints,
                 force_stale_status=True)


SAMPLERS = {
    "clean_refundable": _sample_c1,
    "outside_window_deny": _sample_c2,
    "over_threshold_escalate": _sample_c3,
    "defective_long_window": _sample_c4,
    "digital_downloaded": _sample_c5,
    "gold_tier_trap": _sample_c6,
    "subscription_ambiguity": _sample_c7,
    "duplicate_refund": _sample_c8,
    "flagged_account": _sample_c9,
    "missing_or_wrong_id": _sample_c10,
}

CLASS_NAMES = list(SAMPLERS.keys())


def sample(scenario_class: str, index: int) -> Draw:
    """index is 1-based, 1..N_PER_CLASS."""
    return SAMPLERS[scenario_class](index)


def all_draws() -> list[Draw]:
    return [sample(cls, i) for cls in CLASS_NAMES for i in range(1, N_PER_CLASS + 1)]
