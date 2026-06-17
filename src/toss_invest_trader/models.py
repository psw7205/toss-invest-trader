from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import uuid4

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"LIMIT", "MARKET"}
VALID_TIME_IN_FORCE = {"DAY", "CLS"}
CLIENT_ORDER_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]+$")
INTEGER_DECIMAL_RE = re.compile(r"^\d+$")
POSITIVE_DECIMAL_RE = re.compile(r"^\d+(\.\d+)?$")


@dataclass(frozen=True)
class OrderDraft:
    symbol: str
    side: str
    order_type: str
    quantity: str | None = None
    price: str | None = None
    order_amount: str | None = None
    time_in_force: str = "DAY"
    client_order_id: str | None = None
    confirm_high_value_order: bool = False

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if self.side not in VALID_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_SIDES)}")
        if self.order_type not in VALID_ORDER_TYPES:
            raise ValueError(f"order_type must be one of {sorted(VALID_ORDER_TYPES)}")
        if self.time_in_force not in VALID_TIME_IN_FORCE:
            raise ValueError(f"time_in_force must be one of {sorted(VALID_TIME_IN_FORCE)}")
        if bool(self.quantity) == bool(self.order_amount):
            raise ValueError("exactly one of quantity or order_amount is required")
        if self.order_type == "LIMIT" and not self.price:
            raise ValueError("LIMIT orders require price")
        if self.order_type == "MARKET" and self.price is not None:
            raise ValueError("MARKET orders must not include price")
        if self.order_amount and not (self.side == "BUY" and self.order_type == "MARKET"):
            raise ValueError("order_amount is only supported for BUY MARKET orders")
        _validate_client_order_id(self.client_order_id)
        _validate_integer_decimal("quantity", self.quantity)
        _validate_positive_decimal("order_amount", self.order_amount)
        _validate_positive_decimal("price", self.price)

    def to_api_payload(self) -> dict[str, object]:
        self.validate()
        payload: dict[str, object] = {
            "symbol": self.symbol,
            "side": self.side,
            "orderType": self.order_type,
            "timeInForce": self.time_in_force,
            "confirmHighValueOrder": self.confirm_high_value_order,
        }
        if self.client_order_id:
            payload["clientOrderId"] = self.client_order_id
        if self.quantity:
            payload["quantity"] = self.quantity
        if self.order_amount:
            payload["orderAmount"] = self.order_amount
        if self.price:
            payload["price"] = self.price
        return payload


def generated_client_order_id(prefix: str = "tosstrader") -> str:
    # API max length is 36 chars. Prefix + 8 hex keeps it human-recognizable.
    cleaned_prefix = re.sub(r"[^a-zA-Z0-9\-_]", "-", prefix).strip("-") or "tosstrader"
    return f"{cleaned_prefix}-{uuid4().hex[:8]}"[:36]


def _validate_client_order_id(value: str | None) -> None:
    if value is None:
        return
    if len(value) > 36:
        raise ValueError("client_order_id must be at most 36 characters")
    if not CLIENT_ORDER_ID_RE.fullmatch(value):
        raise ValueError("client_order_id may contain only letters, digits, hyphen, and underscore")


def _validate_integer_decimal(name: str, value: str | None) -> None:
    if value is None:
        return
    if not INTEGER_DECIMAL_RE.fullmatch(value):
        raise ValueError(f"{name} must be a positive integer string")
    if int(value) <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_positive_decimal(name: str, value: str | None) -> None:
    if value is None:
        return
    if not POSITIVE_DECIMAL_RE.fullmatch(value):
        raise ValueError(f"{name} must be a decimal string without exponent or sign")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal string") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
