from __future__ import annotations

import pytest

from toss_invest_trader.models import OrderDraft, generated_client_order_id


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


@pytest.mark.parametrize("quantity", ["1.5", "1e2", "+1", "0", "-1"])
def test_quantity_must_match_openapi_integer_pattern(quantity: str) -> None:
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
