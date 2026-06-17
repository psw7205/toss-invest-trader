from __future__ import annotations

import time
from typing import Any

import httpx

from toss_invest_trader.config import Settings


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
        return self._request("GET", "/api/v1/prices", params={"symbols": ",".join(symbols)}).get(
            "result"
        )

    def holdings(self, *, account: str, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else None
        return self._request("GET", "/api/v1/holdings", account=account, params=params).get(
            "result"
        )

    def orders(self, *, account: str, status: str = "OPEN", symbol: str | None = None) -> Any:
        params = {"status": status}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v1/orders", account=account, params=params).get("result")

    def create_order(self, *, account: str, payload: dict[str, object]) -> Any:
        return self._request("POST", "/api/v1/orders", account=account, json=payload).get("result")

    def cancel_order(self, *, account: str, order_id: str) -> Any:
        return self._request("POST", f"/api/v1/orders/{order_id}/cancel", account=account).get(
            "result"
        )

    def buying_power(self, *, account: str, currency: str) -> Any:
        return self._request(
            "GET", "/api/v1/buying-power", account=account, params={"currency": currency}
        ).get("result")

    def sellable_quantity(self, *, account: str, symbol: str) -> Any:
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
