"""Seeded world generator — Section 5 of prompt.md.

60 customers, 25 products, 180 orders, 20 subscriptions, generated once with
seed 42 and dumped to data/world_seed.sql (committed). `refunds`, `tickets`,
and `audit_log` start empty — they are populated during episodes, and every
episode resets the DB from this dump (NON-NEGOTIABLE 6).

Dates are anchored to a fixed constant, not `datetime.now()`, so the dump is
byte-identical every time this is regenerated.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from ..env.database import connect, dump_to_file, init_schema

SEED = 42
ANCHOR = date(2026, 1, 1)

N_CUSTOMERS = 60
N_PRODUCTS = 25
N_SUBSCRIPTIONS = 20
N_ORDERS = 180

PHYSICAL_CATEGORIES = ["electronics", "home", "apparel", "books", "sports", "kitchen"]
DIGITAL_CATEGORIES = ["digital_media", "software"]

FIRST_NAMES = [
    "Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Jamie",
    "Avery", "Quinn", "Drew", "Skyler", "Reese", "Cameron", "Hayden", "Rowan",
    "Elliot", "Parker", "Emerson", "Finley",
]
LAST_NAMES = [
    "Chen", "Patel", "Garcia", "Nguyen", "Smith", "Kim", "Johnson", "Lopez",
    "Brown", "Davis", "Martin", "Lee", "Walker", "Young", "Hall", "Allen",
    "Wright", "Scott", "Green", "Baker",
]


def _iso(d: date) -> str:
    return d.isoformat()


def _fmt_dt(d: date) -> str:
    return f"{d.isoformat()}T00:00:00"


def generate_world() -> "sqlite3.Connection":  # noqa: F821 - see import inside
    rng = random.Random(SEED)
    conn = connect(":memory:")
    init_schema(conn)

    # customers
    customers = []
    for i in range(1, N_CUSTOMERS + 1):
        cid = f"C{i:04d}"
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        email = f"{name.lower().replace(' ', '.')}.{i}@example.com"
        tier = "gold" if rng.random() < 0.20 else "standard"
        account_status = "flagged" if rng.random() < 0.08 else "active"
        created_at = _fmt_dt(ANCHOR - timedelta(days=rng.randint(30, 900)))
        customers.append((cid, email, name, tier, account_status, created_at))
    conn.executemany(
        "INSERT INTO customers (id, email, name, tier, account_status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        customers,
    )

    # products
    products = []
    for i in range(1, N_PRODUCTS + 1):
        pid = f"P{i:02d}"
        is_digital = i > N_PRODUCTS - 8  # last 8 products are digital
        category = rng.choice(DIGITAL_CATEGORIES) if is_digital else rng.choice(PHYSICAL_CATEGORIES)
        item_type = "digital" if is_digital else "physical"
        unit_cents = rng.randint(500, 25000)
        products.append((pid, f"{category.title()} Item {i}", category, item_type, unit_cents))
    conn.executemany(
        "INSERT INTO products (id, name, category, item_type, unit_cents) VALUES (?, ?, ?, ?, ?)",
        products,
    )

    customer_ids = [c[0] for c in customers]
    product_rows = {p[0]: p for p in products}
    product_ids = list(product_rows.keys())

    # subscriptions: 20 distinct customers
    sub_customers = rng.sample(customer_ids, N_SUBSCRIPTIONS)
    subscriptions = []
    for i, cid in enumerate(sub_customers, start=1):
        sid = f"S{i:02d}"
        started_at = ANCHOR - timedelta(days=rng.randint(120, 720))
        last_renewed_at = ANCHOR - timedelta(days=rng.randint(1, 30))
        subscriptions.append((sid, cid, _fmt_dt(started_at), _fmt_dt(last_renewed_at), "active"))
    conn.executemany(
        "INSERT INTO subscriptions (id, customer_id, started_at, last_renewed_at, status) VALUES (?, ?, ?, ?, ?)",
        subscriptions,
    )

    orders = []
    order_items = []
    order_seq = 1
    item_seq = 1

    def make_order_items(order_id: str, product_choices: list[str]) -> tuple[int, int]:
        nonlocal item_seq
        subtotal = 0
        has_physical = False
        for pid in product_choices:
            _, _, _, item_type, unit_cents = product_rows[pid]
            qty = rng.randint(1, 2)
            downloaded_at = None
            if item_type == "digital" and rng.random() < 0.5:
                downloaded_at = _fmt_dt(ANCHOR - timedelta(days=rng.randint(0, 60)))
            defect = item_type == "physical" and rng.random() < 0.05
            order_items.append(
                (f"I{item_seq:06d}", order_id, pid, qty, unit_cents, downloaded_at, int(defect))
            )
            item_seq += 1
            subtotal += qty * unit_cents
            has_physical = has_physical or item_type == "physical"
        shipping = rng.randint(500, 1500) if has_physical else 0
        return subtotal, shipping

    # subscription cycle orders
    for sid, cid, started_at, last_renewed_at, _ in subscriptions:
        n_cycles = rng.randint(3, 6)
        plan_product = rng.choice(product_ids)
        start_d = date.fromisoformat(started_at[:10])
        renew_d = date.fromisoformat(last_renewed_at[:10])
        span_days = max((renew_d - start_d).days, n_cycles)
        for cycle in range(1, n_cycles + 1):
            oid = f"O{order_seq:04d}"
            order_seq += 1
            offset = int(span_days * cycle / n_cycles)
            placed = start_d + timedelta(days=offset)
            delivered = placed + timedelta(days=rng.randint(1, 5))
            subtotal, shipping = make_order_items(oid, [plan_product])
            orders.append(
                (
                    oid, cid, _fmt_dt(placed), _fmt_dt(delivered), subtotal, shipping,
                    subtotal + shipping, "delivered", 1, sid, cycle,
                )
            )

    # one-off orders fill the remainder
    while order_seq <= N_ORDERS:
        oid = f"O{order_seq:04d}"
        order_seq += 1
        cid = rng.choice(customer_ids)
        n_items = rng.randint(1, 3)
        chosen = [rng.choice(product_ids) for _ in range(n_items)]
        placed = ANCHOR - timedelta(days=rng.randint(1, 400))
        delivered = None
        status = "processing"
        if rng.random() < 0.90:
            delivered = placed + timedelta(days=rng.randint(2, 10))
            status = "delivered"
        subtotal, shipping = make_order_items(oid, chosen)
        orders.append(
            (
                oid, cid, _fmt_dt(placed), _fmt_dt(delivered) if delivered else None,
                subtotal, shipping, subtotal + shipping, status, 0, None, None,
            )
        )

    conn.executemany(
        """INSERT INTO orders
           (id, customer_id, placed_at, delivered_at, subtotal_cents, shipping_cents,
            total_cents, status, is_subscription, subscription_id, cycle_number)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        orders,
    )
    conn.executemany(
        """INSERT INTO order_items
           (id, order_id, product_id, qty, unit_cents, downloaded_at, defect_reported)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        order_items,
    )
    conn.commit()
    return conn


def main() -> None:
    conn = generate_world()
    dump_to_file(conn)
    conn.close()
    print("wrote data/world_seed.sql")


if __name__ == "__main__":
    main()
