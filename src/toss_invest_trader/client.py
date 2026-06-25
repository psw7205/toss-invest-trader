from __future__ import annotations

import re
import time
from datetime import date as Date
from datetime import datetime
from typing import Any

import httpx

from toss_invest_trader.config import Settings

VALID_ORDER_STATUSES = {"OPEN", "CLOSED"}
VALID_CANDLE_INTERVALS = {"1m", "1d"}
SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TossInvestError(RuntimeError):
    def __init__(
        self, message: str, *, status_code: int | None = None, payload: Any = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class TossInvestClient:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._client = httpx.Client(
            base_url=settings.base_url,
            timeout=httpx.Timeout(20.0, connect=10.0),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TossInvestClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token
        response = self._client.post(
            "/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        payload = _parse_response(response)
        token = str(payload["access_token"])
        self._token = token
        self._token_expires_at = now + int(payload.get("expires_in", 0))
        return token

    def accounts(self) -> Any:
        return self._request("GET", "/api/v1/accounts").get("result")

    def prices(self, symbols: list[str]) -> Any:
        if not symbols:
            raise ValueError("symbols is required")
        for symbol in symbols:
            _validate_symbol(symbol)
        return self._request("GET", "/api/v1/prices", params={"symbols": ",".join(symbols)}).get(
            "result"
        )

    def quote(self, symbol: str) -> Any:
        _validate_symbol(symbol)
        quotes = self.prices([symbol])
        if isinstance(quotes, list):
            return quotes[0] if quotes else None
        return quotes

    def candles(
        self,
        symbol: str,
        interval: str,
        *,
        count: int = 100,
        before: str | datetime | None = None,
        adjusted: bool = True,
    ) -> Any:
        _validate_symbol(symbol)
        if interval not in VALID_CANDLE_INTERVALS:
            raise ValueError("interval must be one of ['1d', '1m']")
        if not 1 <= count <= 200:
            raise ValueError("count must be between 1 and 200")
        params: dict[str, object] = {
            "symbol": symbol,
            "interval": interval,
            "count": count,
            "adjusted": adjusted,
        }
        if before is not None:
            params["before"] = _format_datetime(before)
        return self._request("GET", "/api/v1/candles", params=params).get("result")

    def price_limits(self, symbol: str) -> Any:
        _validate_symbol(symbol)
        return self._request("GET", "/api/v1/price-limits", params={"symbol": symbol}).get("result")

    def market_calendar(self, market: str, date: str | Date | None = None) -> Any:
        normalized = market.upper()
        if normalized not in {"KR", "US"}:
            raise ValueError("market must be one of ['KR', 'US']")
        params = {"date": _format_date(date)} if date is not None else None
        return self._request("GET", f"/api/v1/market-calendar/{normalized}", params=params).get(
            "result"
        )

    def holdings(self, *, account: str, symbol: str | None = None) -> Any:
        if symbol is not None:
            _validate_symbol(symbol)
        params = {"symbol": symbol} if symbol else None
        return self._request("GET", "/api/v1/holdings", account=account, params=params).get(
            "result"
        )

    def orders(
        self,
        *,
        account: str,
        status: str = "OPEN",
        symbol: str | None = None,
        from_date: str | Date | None = None,
        to_date: str | Date | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Any:
        if status not in VALID_ORDER_STATUSES:
            raise ValueError("status must be one of ['CLOSED', 'OPEN']")
        if symbol is not None:
            _validate_symbol(symbol)
        if limit is not None and not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        params: dict[str, object] = {"status": status}
        if symbol:
            params["symbol"] = symbol
        if from_date is not None:
            params["from"] = _format_date(from_date)
        if to_date is not None:
            params["to"] = _format_date(to_date)
        if cursor:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/api/v1/orders", account=account, params=params).get("result")

    def create_order(self, *, account: str, payload: dict[str, object]) -> Any:
        return self._request("POST", "/api/v1/orders", account=account, json=payload).get("result")

    def cancel_order(self, *, account: str, order_id: str) -> Any:
        return self._request(
            "POST", f"/api/v1/orders/{order_id}/cancel", account=account, json={}
        ).get("result")

    def buying_power(self, *, account: str, currency: str) -> Any:
        return self._request(
            "GET", "/api/v1/buying-power", account=account, params={"currency": currency}
        ).get("result")

    def sellable_quantity(self, *, account: str, symbol: str) -> Any:
        _validate_symbol(symbol)
        return self._request(
            "GET", "/api/v1/sellable-quantity", account=account, params={"symbol": symbol}
        ).get("result")

    def _request(self, method: str, path: str, *, account: str | None = None, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.token()}"
        if account is not None:
            headers["X-Tossinvest-Account"] = str(account)
        response = self._client.request(method, path, headers=headers, **kwargs)
        return _parse_response(response)


def _parse_response(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    if response.is_error:
        raise TossInvestError(
            f"Toss Invest API request failed: HTTP {response.status_code}",
            status_code=response.status_code,
            payload=payload,
        )
    return payload


def _validate_symbol(symbol: str) -> None:
    if not symbol:
        raise ValueError("symbol is required")
    if not SYMBOL_RE.fullmatch(symbol):
        raise ValueError("symbol may contain only letters, digits, dot, and hyphen")


def _format_date(value: str | Date) -> str:
    if isinstance(value, str):
        if not DATE_RE.fullmatch(value):
            raise ValueError("date must use YYYY-MM-DD format")
        try:
            Date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must use YYYY-MM-DD format") from exc
        return value
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def _format_datetime(value: str | datetime) -> str:
    if isinstance(value, str):
        if "T" not in value:
            raise ValueError("datetime must use ISO 8601 format")
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("datetime must use ISO 8601 format") from exc
        return value
    return value.isoformat()
