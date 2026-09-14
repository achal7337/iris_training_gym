"""SQLite schema (Section 5 of prompt.md) and reset-from-dump.

`refunds` and `audit_log` are append-only within an episode — nothing is
ever deleted; a fresh episode instead resets the whole DB from the committed
world dump (NON-NEGOTIABLE 6, deterministic replay).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORLD_SEED_PATH = REPO_ROOT / "data" / "world_seed.sql"

TABLES = [
    "customers",
    "products",
    "orders",
    "order_items",
    "subscriptions",
    "refunds",
    "tickets",
    "audit_log",
]

SCHEMA_SQL = """
CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('standard', 'gold')),
    account_status TEXT NOT NULL CHECK (account_status IN ('active', 'flagged')),
    created_at TEXT NOT NULL
);

CREATE TABLE products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK (item_type IN ('physical', 'digital')),
    unit_cents INTEGER NOT NULL
);

CREATE TABLE subscriptions (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    started_at TEXT NOT NULL,
    last_renewed_at TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    placed_at TEXT NOT NULL,
    delivered_at TEXT,
    subtotal_cents INTEGER NOT NULL,
    shipping_cents INTEGER NOT NULL,
    total_cents INTEGER NOT NULL,
    status TEXT NOT NULL,
    is_subscription INTEGER NOT NULL DEFAULT 0,
    subscription_id TEXT REFERENCES subscriptions(id),
    cycle_number INTEGER
);

CREATE TABLE order_items (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    qty INTEGER NOT NULL,
    unit_cents INTEGER NOT NULL,
    downloaded_at TEXT,
    defect_reported INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE refunds (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    amount_cents INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    approved_by TEXT
);

CREATE TABLE tickets (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    order_id_claimed TEXT,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    args_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    blocked INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def dump_to_file(conn: sqlite3.Connection, path: str | Path = WORLD_SEED_PATH) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for line in conn.iterdump():
            f.write(f"{line}\n")


def apply_setup(conn: sqlite3.Connection, setup_sql: list[tuple[str, list]]) -> None:
    """Applies a scenario's (sql, params) fixture on top of the reset world
    (Section 6: "sample facts under constraints that guarantee the class")."""
    for sql, params in setup_sql:
        conn.execute(sql, params)
    conn.commit()


def reset_from_dump(conn: sqlite3.Connection, path: str | Path = WORLD_SEED_PATH) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    with open(path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
