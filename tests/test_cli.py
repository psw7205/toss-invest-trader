from __future__ import annotations

import argparse
import json

import pytest

from toss_invest_trader.cli import _resolve_account, main
from toss_invest_trader.client import TossInvestError


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOSSINVEST_CLIENT_ID", "cid")
    monkeypatch.setenv("TOSSINVEST_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TOSSINVEST_TRADING_MODE", "paper")
    monkeypatch.delenv("TOSSINVEST_ACCOUNT", raising=False)
    monkeypatch.delenv("TOSSINVEST_BASE_URL", raising=False)
    monkeypatch.delenv("TOSSINVEST_ALLOW_CUSTOM_BASE_URL", raising=False)
    monkeypatch.delenv("TOSSINVEST_DEBUG_API_ERRORS", raising=False)


class FakeClient:
    def __init__(self, accounts: list[dict[str, object]]) -> None:
        self._accounts = accounts

    def accounts(self) -> list[dict[str, object]]:
        return self._accounts


def test_resolve_account_uses_explicit_override() -> None:
    args = argparse.Namespace(account="7")

    assert _resolve_account(args, FakeClient([])) == "7"


def test_resolve_account_auto_selects_single_api_account() -> None:
    args = argparse.Namespace(account=None)

    assert (
        _resolve_account(args, FakeClient([{"accountSeq": 1, "accountType": "BROKERAGE"}])) == "1"
    )


def test_resolve_account_rejects_zero_accounts() -> None:
    args = argparse.Namespace(account=None)

    with pytest.raises(RuntimeError, match="no Toss Invest accounts"):
        _resolve_account(args, FakeClient([]))


def test_resolve_account_rejects_multiple_accounts() -> None:
    args = argparse.Namespace(account=None)

    with pytest.raises(RuntimeError, match="multiple accounts found"):
        _resolve_account(
            args,
            FakeClient(
                [
                    {"accountSeq": 1, "accountType": "BROKERAGE"},
                    {"accountSeq": 2, "accountType": "BROKERAGE"},
                ]
            ),
        )


def test_order_command_is_dry_run_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(
        [
            "order",
            "--symbol",
            "AAPL",
            "--side",
            "BUY",
            "--order-type",
            "LIMIT",
            "--quantity",
            "1",
            "--price",
            "180.00",
            "--client-order-id",
            "manual-aapl-001",
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert '"dryRun": true' in out
    assert '"operation": "createOrder"' in out
    assert '"endpoint": "/api/v1/orders"' in out
    assert '"preflight"' in out
    assert '"clientOrderId": "manual-aapl-001"' in out


def test_order_dry_run_does_not_require_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TOSSINVEST_CLIENT_ID", raising=False)
    monkeypatch.delenv("TOSSINVEST_CLIENT_SECRET", raising=False)

    rc = main(
        [
            "order",
            "--symbol",
            "AAPL",
            "--side",
            "BUY",
            "--order-type",
            "MARKET",
            "--quantity",
            "1",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dryRun"] is True
    assert payload["preflight"]["checks"]["idempotency"]["clientOrderIdPresent"] is False


def test_cancel_command_is_dry_run_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["cancel", "order-123"])

    assert rc == 0
    out = capsys.readouterr().out
    assert '"dryRun": true' in out
    assert '"operation": "cancelOrder"' in out
    assert '"endpoint": "/api/v1/orders/order-123/cancel"' in out
    assert '"wouldCancelOrderId": "order-123"' in out


def test_read_only_market_data_commands_use_client(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, object]] = []

    class MarketDataClient:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def __enter__(self) -> MarketDataClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def quote(self, symbol: str) -> object:
            calls.append(("quote", symbol))
            return {"symbol": symbol}

        def candles(
            self,
            symbol: str,
            interval: str,
            *,
            count: int,
            before: str | None,
            adjusted: bool,
        ) -> object:
            calls.append(
                (
                    "candles",
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "count": count,
                        "before": before,
                        "adjusted": adjusted,
                    },
                )
            )
            return {"candles": []}

        def price_limits(self, symbol: str) -> object:
            calls.append(("price_limits", symbol))
            return {"symbol": symbol}

        def market_calendar(self, market: str, date: str | None = None) -> object:
            calls.append(("market_calendar", {"market": market, "date": date}))
            return {"market": market}

    monkeypatch.setattr("toss_invest_trader.cli.TossInvestClient", MarketDataClient)

    assert main(["quote", "AAPL"]) == 0
    assert main(["candles", "AAPL", "--interval", "1d", "--count", "20", "--raw"]) == 0
    assert main(["price-limits", "AAPL"]) == 0
    assert main(["market-calendar", "US", "--date", "2026-01-02"]) == 0

    capsys.readouterr()
    assert calls == [
        ("quote", "AAPL"),
        (
            "candles",
            {
                "symbol": "AAPL",
                "interval": "1d",
                "count": 20,
                "before": None,
                "adjusted": False,
            },
        ),
        ("price_limits", "AAPL"),
        ("market_calendar", {"market": "US", "date": "2026-01-02"}),
    ]


def test_orders_command_passes_filters(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[dict[str, object]] = []

    class OrdersClient:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def __enter__(self) -> OrdersClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def orders(self, **kwargs: object) -> object:
            calls.append(kwargs)
            return {"orders": []}

    monkeypatch.setattr("toss_invest_trader.cli.TossInvestClient", OrdersClient)

    rc = main(
        [
            "orders",
            "--account",
            "7",
            "--status",
            "CLOSED",
            "--symbol",
            "AAPL",
            "--from-date",
            "2026-01-01",
            "--to-date",
            "2026-01-31",
            "--cursor",
            "cursor-1",
            "--limit",
            "50",
        ]
    )

    assert rc == 0
    capsys.readouterr()
    assert calls == [
        {
            "account": "7",
            "status": "CLOSED",
            "symbol": "AAPL",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "cursor": "cursor-1",
            "limit": 50,
        }
    ]


def test_live_order_requires_live_mode(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(
        [
            "order",
            "--symbol",
            "AAPL",
            "--side",
            "BUY",
            "--order-type",
            "LIMIT",
            "--quantity",
            "1",
            "--price",
            "180.00",
            "--client-order-id",
            "manual-aapl-001",
            "--execute",
            "--i-understand-real-order",
        ]
    )

    assert rc == 1
    assert "TOSSINVEST_TRADING_MODE=live" in capsys.readouterr().err


def test_live_order_requires_ack(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TOSSINVEST_TRADING_MODE", "live")
    rc = main(
        [
            "order",
            "--symbol",
            "AAPL",
            "--side",
            "BUY",
            "--order-type",
            "LIMIT",
            "--quantity",
            "1",
            "--price",
            "180.00",
            "--client-order-id",
            "manual-aapl-001",
            "--execute",
        ]
    )

    assert rc == 1
    assert "--i-understand-real-order" in capsys.readouterr().err


def test_live_cancel_requires_live_mode(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["cancel", "order-123", "--execute", "--i-understand-real-order"])

    assert rc == 1
    assert "TOSSINVEST_TRADING_MODE=live" in capsys.readouterr().err


def test_live_cancel_requires_ack(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TOSSINVEST_TRADING_MODE", "live")

    rc = main(["cancel", "order-123", "--execute"])

    assert rc == 1
    assert "--i-understand-real-order" in capsys.readouterr().err


def test_live_order_requires_client_order_id(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TOSSINVEST_TRADING_MODE", "live")
    rc = main(
        [
            "order",
            "--symbol",
            "AAPL",
            "--side",
            "BUY",
            "--order-type",
            "MARKET",
            "--quantity",
            "1",
            "--execute",
            "--i-understand-real-order",
        ]
    )

    assert rc == 1
    assert "--client-order-id or --generate-client-order-id" in capsys.readouterr().err


def test_guard_failure_does_not_create_client(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingClient:
        def __init__(self, *_: object, **__: object) -> None:
            raise AssertionError("client should not be created before guard passes")

    monkeypatch.setattr("toss_invest_trader.cli.TossInvestClient", FailingClient)

    rc = main(["cancel", "order-123", "--execute", "--i-understand-real-order"])

    assert rc == 1
    assert "TOSSINVEST_TRADING_MODE=live" in capsys.readouterr().err


def test_api_error_payload_is_redacted_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingClient:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def __enter__(self) -> FailingClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def accounts(self) -> object:
            raise TossInvestError(
                "request failed",
                status_code=400,
                payload={
                    "errorCode": "BAD_REQUEST",
                    "message": "bad account",
                    "client_secret": "secret-value",
                    "accountSeq": "12345678",
                },
            )

    monkeypatch.setattr("toss_invest_trader.cli.TossInvestClient", FailingClient)

    rc = main(["accounts"])

    err = capsys.readouterr().err
    assert rc == 1
    assert "BAD_REQUEST" in err
    assert "secret-value" not in err
    assert "12345678" not in err
