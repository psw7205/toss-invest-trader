from __future__ import annotations

import argparse

import pytest

from toss_invest_trader.cli import _resolve_account, main


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOSSINVEST_CLIENT_ID", "cid")
    monkeypatch.setenv("TOSSINVEST_CLIENT_SECRET", "secret")
    monkeypatch.delenv("TOSSINVEST_ACCOUNT", raising=False)


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
    assert '"clientOrderId": "manual-aapl-001"' in out


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
