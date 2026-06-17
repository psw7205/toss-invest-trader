from __future__ import annotations

import httpx

from toss_invest_trader.client import TossInvestClient
from toss_invest_trader.config import Settings


def test_client_adds_auth_and_account_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/oauth2/token":
            return httpx.Response(
                200, json={"access_token": "token-1", "token_type": "Bearer", "expires_in": 3600}
            )
        assert request.headers["authorization"] == "Bearer token-1"
        assert request.headers["x-tossinvest-account"] == "7"
        return httpx.Response(
            200, json={"result": {"orders": [], "nextCursor": None, "hasNext": False}}
        )

    settings = Settings(client_id="cid", client_secret="secret")
    client = TossInvestClient(settings, transport=httpx.MockTransport(handler))

    try:
        result = client.orders(account="7")
    finally:
        client.close()

    assert result == {"orders": [], "nextCursor": None, "hasNext": False}
    assert [request.url.path for request in seen] == ["/oauth2/token", "/api/v1/orders"]
    assert seen[0].content == b"grant_type=client_credentials&client_id=cid&client_secret=secret"


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
