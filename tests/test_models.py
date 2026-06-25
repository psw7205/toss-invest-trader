from __future__ import annotations

import pytest

from toss_invest_trader.models import (
    OrderDraft,
    generated_client_order_id,
    preflight_cancel_order,
    preflight_create_order,
)


def test_limit_order_payload() -> None:
    payload = OrderDraft(
        symbol="AAPL",
        side="BUY",
        order_type="LIMIT",
        quantity="1",
        price="180.00",
        client_order_id="manual-aapl-001",
    ).to_api_payload()

    assert payload == {
        "symbol": "AAPL",
        "side": "BUY",
        "orderType": "LIMIT",
        "timeInForce": "DAY",
        "confirmHighValueOrder": False,
        "clientOrderId": "manual-aapl-001",
        "quantity": "1",
        "price": "180.00",
    }


def test_market_order_rejects_price() -> None:
    with pytest.raises(ValueError, match="MARKET orders must not include price"):
        OrderDraft(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity="1",
            price="180.00",
        ).to_api_payload()


def test_requires_exactly_one_quantity_or_amount() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        OrderDraft(symbol="AAPL", side="BUY", order_type="MARKET").to_api_payload()

    with pytest.raises(ValueError, match="exactly one"):
        OrderDraft(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity="1",
            order_amount="100",
        ).to_api_payload()


def test_amount_based_order_is_buy_market_only() -> None:
    with pytest.raises(ValueError, match="BUY MARKET"):
        OrderDraft(
            symbol="AAPL",
            side="SELL",
            order_type="MARKET",
            order_amount="100",
        ).to_api_payload()


def test_quantity_accepts_openapi_decimal_pattern() -> None:
    payload = OrderDraft(
        symbol="AAPL",
        side="BUY",
        order_type="MARKET",
        quantity="1.5",
    ).to_api_payload()

    assert payload["quantity"] == "1.5"


@pytest.mark.parametrize("quantity", ["1e2", "+1", "0", "-1", "1.", ".1"])
def test_quantity_must_match_openapi_decimal_pattern(quantity: str) -> None:
    with pytest.raises(ValueError, match="quantity"):
        OrderDraft(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity=quantity,
        ).to_api_payload()


@pytest.mark.parametrize("value", ["1e2", "+1", "-1", "0", "1.", ".1"])
def test_price_must_match_openapi_decimal_pattern(value: str) -> None:
    with pytest.raises(ValueError, match="price"):
        OrderDraft(
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            quantity="1",
            price=value,
        ).to_api_payload()


@pytest.mark.parametrize("client_order_id", ["has space", "bad/slash", "x" * 37])
def test_client_order_id_must_match_openapi_pattern(client_order_id: str) -> None:
    with pytest.raises(ValueError, match="client_order_id"):
        OrderDraft(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity="1",
            client_order_id=client_order_id,
        ).to_api_payload()


def test_generated_client_order_id_matches_openapi_pattern() -> None:
    value = generated_client_order_id("toss trader")

    assert len(value) <= 36
    assert value.startswith("toss-trader-")
    assert (
        OrderDraft(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity="1",
            client_order_id=value,
        ).to_api_payload()["clientOrderId"]
        == value
    )


def test_create_order_preflight_requires_idempotency_for_live() -> None:
    preflight = preflight_create_order(
        payload={
            "symbol": "AAPL",
            "side": "BUY",
            "orderType": "MARKET",
            "quantity": "1",
            "confirmHighValueOrder": False,
        },
        execution_mode="live",
        live_trading_enabled=True,
        real_order_acknowledged=True,
    )

    assert preflight.passed is False
    assert preflight.checks["idempotency"] == {
        "clientOrderIdRequired": True,
        "clientOrderIdPresent": False,
    }
    assert preflight.errors == (
        "live order requires --client-order-id or --generate-client-order-id",
    )


def test_create_order_preflight_reports_high_value_confirmation() -> None:
    preflight = preflight_create_order(
        payload={
            "symbol": "AAPL",
            "side": "BUY",
            "orderType": "MARKET",
            "quantity": "1",
            "clientOrderId": "manual-aapl-001",
            "confirmHighValueOrder": True,
        },
        execution_mode="dry-run",
        live_trading_enabled=False,
        real_order_acknowledged=False,
    )

    assert preflight.passed is True
    assert preflight.checks["risk"] == {
        "highValueConfirmationAcknowledged": True,
    }


def test_cancel_order_preflight_reports_cancel_operation() -> None:
    preflight = preflight_cancel_order(
        order_id="order-123",
        execution_mode="dry-run",
        live_trading_enabled=False,
        real_order_acknowledged=False,
    )

    assert preflight.to_dict()["operation"] == "cancelOrder"
    assert preflight.to_dict()["endpoint"] == "/api/v1/orders/order-123/cancel"
    assert preflight.passed is True
