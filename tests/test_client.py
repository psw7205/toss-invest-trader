from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from toss_invest_trader.client import TossInvestClient
from toss_invest_trader.config import Settings


class TossMockTransport:
    def __init__(self, handler: Callable[[httpx.Request], httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self._handler = handler

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/oauth2/token":
            return httpx.Response(
                200, json={"access_token": "token-1", "token_type": "Bearer", "expires_in": 3600}
            )
        if self._handler is not None:
            return self._handler(request)
        return httpx.Response(200, json={"result": []})


def test_client_adds_auth_and_account_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer token-1"
        assert request.headers["x-tossinvest-account"] == "7"
        return httpx.Response(
            200, json={"result": {"orders": [], "nextCursor": None, "hasNext": False}}
        )

    mock = TossMockTransport(handler)
    settings = Settings(client_id="cid", client_secret="secret")
    client = TossInvestClient(settings, transport=mock.transport())

    try:
        result = client.orders(account="7")
    finally:
        client.close()

    assert result == {"orders": [], "nextCursor": None, "hasNext": False}
    assert [request.url.path for request in mock.requests] == ["/oauth2/token", "/api/v1/orders"]
    assert (
        mock.requests[0].content
        == b"grant_type=client_credentials&client_id=cid&client_secret=secret"
    )


def test_token_is_cached() -> None:
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if request.url.path == "/oauth2/token":
            token_calls += 1
            return httpx.Response(
                200, json={"access_token": "token-1", "token_type": "Bearer", "expires_in": 3600}
            )
        return httpx.Response(200, json={"result": []})

    client = TossInvestClient(
        Settings(client_id="cid", client_secret="secret"), transport=httpx.MockTransport(handler)
    )
    try:
        client.accounts()
        client.accounts()
    finally:
        client.close()

    assert token_calls == 1


def test_orders_passes_optional_filters() -> None:
    mock = TossMockTransport(
        lambda request: httpx.Response(
            200, json={"result": {"query": dict(request.url.params.multi_items())}}
        )
    )
    client = TossInvestClient(
        Settings(client_id="cid", client_secret="secret"), transport=mock.transport()
    )

    try:
        result = client.orders(
            account="7",
            status="CLOSED",
            symbol="AAPL",
            from_date="2026-01-01",
            to_date="2026-01-31",
            cursor="cursor-1",
            limit=50,
        )
    finally:
        client.close()

    assert result["query"] == {
        "status": "CLOSED",
        "symbol": "AAPL",
        "from": "2026-01-01",
        "to": "2026-01-31",
        "cursor": "cursor-1",
        "limit": "50",
    }


def test_orders_validate_openapi_filters_before_http() -> None:
    mock = TossMockTransport()
    client = TossInvestClient(
        Settings(client_id="cid", client_secret="secret"), transport=mock.transport()
    )

    try:
        with pytest.raises(ValueError, match="status"):
            client.orders(account="7", status="DONE")
        with pytest.raises(ValueError, match="symbol"):
            client.orders(account="7", symbol="bad symbol")
        with pytest.raises(ValueError, match="date"):
            client.orders(account="7", from_date="20260101")
        with pytest.raises(ValueError, match="limit"):
            client.orders(account="7", limit=101)
    finally:
        client.close()

    assert mock.requests == []


def test_quote_uses_single_symbol_prices_request() -> None:
    mock = TossMockTransport(
        lambda request: httpx.Response(
            200,
            json={"result": [{"symbol": request.url.params["symbols"], "price": "180.00"}]},
        )
    )
    client = TossInvestClient(
        Settings(client_id="cid", client_secret="secret"), transport=mock.transport()
    )

    try:
        result = client.quote("AAPL")
    finally:
        client.close()

    assert result == {"symbol": "AAPL", "price": "180.00"}
    assert mock.requests[-1].url.path == "/api/v1/prices"
    assert mock.requests[-1].url.params["symbols"] == "AAPL"


def test_candles_passes_openapi_params() -> None:
    mock = TossMockTransport(
        lambda request: httpx.Response(
            200, json={"result": {"query": dict(request.url.params.multi_items())}}
        )
    )
    client = TossInvestClient(
        Settings(client_id="cid", client_secret="secret"), transport=mock.transport()
    )

    try:
        result = client.candles(
            "AAPL",
            "1d",
            count=25,
            before="2026-01-31T00:00:00Z",
            adjusted=False,
        )
    finally:
        client.close()

    assert result["query"] == {
        "symbol": "AAPL",
        "interval": "1d",
        "count": "25",
        "before": "2026-01-31T00:00:00Z",
        "adjusted": "false",
    }


def test_market_data_validates_openapi_params_before_http() -> None:
    mock = TossMockTransport()
    client = TossInvestClient(
        Settings(client_id="cid", client_secret="secret"), transport=mock.transport()
    )

    try:
        with pytest.raises(ValueError, match="symbol"):
            client.prices(["AAPL", "bad symbol"])
        with pytest.raises(ValueError, match="count"):
            client.candles("AAPL", "1d", count=201)
        with pytest.raises(ValueError, match="datetime"):
            client.candles("AAPL", "1d", before="2026-01-31")
        with pytest.raises(ValueError, match="date"):
            client.market_calendar("US", date="2026-01-31T00:00:00Z")
        with pytest.raises(ValueError, match="symbol"):
            client.sellable_quantity(account="7", symbol="AAPL!")
    finally:
        client.close()

    assert mock.requests == []


def test_price_limits_and_market_calendar_wrappers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "path": request.url.path,
                    "query": dict(request.url.params.multi_items()),
                }
            },
        )

    mock = TossMockTransport(handler)
    client = TossInvestClient(
        Settings(client_id="cid", client_secret="secret"), transport=mock.transport()
    )

    try:
        limits = client.price_limits("AAPL")
        calendar = client.market_calendar("US", date="2026-01-02")
    finally:
        client.close()

    assert limits == {"path": "/api/v1/price-limits", "query": {"symbol": "AAPL"}}
    assert calendar == {"path": "/api/v1/market-calendar/US", "query": {"date": "2026-01-02"}}


def test_cancel_order_sends_empty_json_body() -> None:
    mock = TossMockTransport(lambda request: httpx.Response(200, json={"result": {"ok": True}}))
    client = TossInvestClient(
        Settings(client_id="cid", client_secret="secret"), transport=mock.transport()
    )

    try:
        result = client.cancel_order(account="7", order_id="order-123")
    finally:
        client.close()

    cancel_request = mock.requests[-1]
    assert result == {"ok": True}
    assert cancel_request.method == "POST"
    assert cancel_request.url.path == "/api/v1/orders/order-123/cancel"
    assert cancel_request.headers["content-type"] == "application/json"
    assert json.loads(cancel_request.content) == {}
