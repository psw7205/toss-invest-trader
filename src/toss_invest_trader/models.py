from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import uuid4

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"LIMIT", "MARKET"}
VALID_TIME_IN_FORCE = {"DAY", "CLS"}
CLIENT_ORDER_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]+$")
POSITIVE_DECIMAL_RE = re.compile(r"^\d+(\.\d+)?$")
OrderOperation = Literal["createOrder", "cancelOrder"]


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
        _validate_positive_decimal("quantity", self.quantity)
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


@dataclass(frozen=True)
class PreflightResult:
    operation: OrderOperation
    method: str
    endpoint: str
    execution_mode: str
    checks: dict[str, object]
    errors: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            raise RuntimeError("; ".join(self.errors))

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "operation": self.operation,
            "method": self.method,
            "endpoint": self.endpoint,
            "executionMode": self.execution_mode,
            "checks": self.checks,
            "errors": list(self.errors),
        }


def preflight_create_order(
    *,
    payload: dict[str, object],
    execution_mode: str,
    live_trading_enabled: bool,
    real_order_acknowledged: bool,
) -> PreflightResult:
    client_order_id_present = bool(payload.get("clientOrderId"))
    high_value_confirmation = bool(payload.get("confirmHighValueOrder"))
    errors: list[str] = []
    if execution_mode == "live":
        if not live_trading_enabled:
            errors.append("live submission requires TOSSINVEST_TRADING_MODE=live")
        if not real_order_acknowledged:
            errors.append("live submission requires --i-understand-real-order")
        if not client_order_id_present:
            errors.append("live order requires --client-order-id or --generate-client-order-id")

    return PreflightResult(
        operation="createOrder",
        method="POST",
        endpoint="/api/v1/orders",
        execution_mode=execution_mode,
        checks={
            "liveTradingEnabled": live_trading_enabled,
            "realOrderAcknowledged": real_order_acknowledged,
            "idempotency": {
                "clientOrderIdRequired": execution_mode == "live",
                "clientOrderIdPresent": client_order_id_present,
            },
            "risk": {
                "highValueConfirmationAcknowledged": high_value_confirmation,
            },
        },
        errors=tuple(errors),
    )


def preflight_cancel_order(
    *,
    order_id: str,
    execution_mode: str,
    live_trading_enabled: bool,
    real_order_acknowledged: bool,
) -> PreflightResult:
    errors: list[str] = []
    if execution_mode == "live":
        if not live_trading_enabled:
            errors.append("live submission requires TOSSINVEST_TRADING_MODE=live")
        if not real_order_acknowledged:
            errors.append("live submission requires --i-understand-real-order")
    if not order_id:
        errors.append("order_id is required")

    return PreflightResult(
        operation="cancelOrder",
        method="POST",
        endpoint=f"/api/v1/orders/{order_id}/cancel",
        execution_mode=execution_mode,
        checks={
            "liveTradingEnabled": live_trading_enabled,
            "realOrderAcknowledged": real_order_acknowledged,
            "idempotency": {
                "clientOrderIdRequired": False,
                "clientOrderIdPresent": None,
            },
            "risk": {
                "highValueConfirmationAcknowledged": None,
            },
        },
        errors=tuple(errors),
    )


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
