"""Pydantic models mirroring the SQLite schema in Section 5 of prompt.md.

These are the shapes tool return values are validated against. The agent
never sees a raw DB row — only these.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Tier = Literal["standard", "gold"]
AccountStatus = Literal["active", "flagged"]
ItemType = Literal["physical", "digital"]


class Customer(BaseModel):
    id: str
    email: str
    name: str
    tier: Tier
    account_status: AccountStatus
    created_at: str


class Product(BaseModel):
    id: str
    name: str
    category: str
    item_type: ItemType
    unit_cents: int


class OrderItem(BaseModel):
    id: str
    order_id: str
    product_id: str
    qty: int
    unit_cents: int
    downloaded_at: Optional[str] = None
    defect_reported: bool = False


class Order(BaseModel):
    id: str
    customer_id: str
    placed_at: str
    delivered_at: Optional[str] = None
    subtotal_cents: int
    shipping_cents: int
    total_cents: int
    status: str
    is_subscription: bool
    subscription_id: Optional[str] = None
    cycle_number: Optional[int] = None
    items: list[OrderItem] = []


class Subscription(BaseModel):
    id: str
    customer_id: str
    started_at: str
    last_renewed_at: str
    status: str


class Refund(BaseModel):
    id: str
    order_id: str
    amount_cents: int
    reason: str
    created_at: str
    created_by: str
    approved_by: Optional[str] = None


class Ticket(BaseModel):
    id: str
    customer_id: str
    order_id_claimed: Optional[str] = None
    body: str
    created_at: str


class AuditLogEntry(BaseModel):
    id: int
    ts: str
    actor: str
    action: str
    args_json: str
    result_json: str
    blocked: bool
