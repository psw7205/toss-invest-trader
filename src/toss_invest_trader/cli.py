from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Protocol

from toss_invest_trader.client import TossInvestClient, TossInvestError
from toss_invest_trader.config import load_settings
from toss_invest_trader.models import OrderDraft, generated_client_order_id


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, ValueError, TossInvestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if isinstance(exc, TossInvestError) and exc.payload is not None:
            print(json.dumps(exc.payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tosstrader")
    parser.add_argument("--env-file", help="Path to server-local .env")
    sub = parser.add_subparsers(required=True)

    _add_simple(sub, "accounts", "List accountSeq values", cmd_accounts)

    prices = _add_simple(sub, "prices", "Get current prices", cmd_prices)
    prices.add_argument("symbols", nargs="+", help="Symbols such as 005930 AAPL")

    holdings = _add_accounted(sub, "holdings", "Get holdings", cmd_holdings)
    holdings.add_argument("--symbol")

    orders = _add_accounted(sub, "orders", "List orders", cmd_orders)
    orders.add_argument("--status", choices=["OPEN", "CLOSED"], default="OPEN")
    orders.add_argument("--symbol")

    buying = _add_accounted(sub, "buying-power", "Get cash buying power", cmd_buying_power)
    buying.add_argument("--currency", choices=["KRW", "USD"], required=True)

    sellable = _add_accounted(sub, "sellable", "Get sellable quantity", cmd_sellable)
    sellable.add_argument("--symbol", required=True)

    order = _add_accounted(sub, "order", "Create an order; dry-run by default", cmd_order)
    order.add_argument("--symbol", required=True)
    order.add_argument("--side", choices=["BUY", "SELL"], required=True)
    order.add_argument("--order-type", choices=["LIMIT", "MARKET"], required=True)
    order.add_argument("--quantity")
    order.add_argument("--order-amount")
    order.add_argument("--price")
    order.add_argument("--time-in-force", choices=["DAY", "CLS"], default="DAY")
    order.add_argument("--client-order-id")
    order.add_argument("--generate-client-order-id", action="store_true")
    order.add_argument("--confirm-high-value-order", action="store_true")
    order.add_argument("--execute", action="store_true", help="Actually submit POST /api/v1/orders")
    order.add_argument("--i-understand-real-order", action="store_true")

    cancel = _add_accounted(sub, "cancel", "Cancel an order", cmd_cancel)
    cancel.add_argument("order_id")
    cancel.add_argument("--execute", action="store_true")
    cancel.add_argument("--i-understand-real-order", action="store_true")
    return parser


def _add_simple(
    sub: argparse._SubParsersAction[argparse.ArgumentParser], name: str, help_: str, func: Any
):
    command = sub.add_parser(name, help=help_)
    command.set_defaults(func=func)
    return command


def _add_accounted(
    sub: argparse._SubParsersAction[argparse.ArgumentParser], name: str, help_: str, func: Any
):
    command = _add_simple(sub, name, help_, func)
    command.add_argument(
        "--account",
        help="accountSeq override. If omitted, auto-selects the only account from API.",
    )
    return command


def _settings(args: argparse.Namespace):
    return load_settings(args.env_file)


class AccountSource(Protocol):
    def accounts(self) -> Any: ...


def _resolve_account(args: argparse.Namespace, client: AccountSource) -> str:
    if args.account:
        return str(args.account)

    accounts = client.accounts()
    if not accounts:
        raise RuntimeError("no Toss Invest accounts returned by GET /api/v1/accounts")
    if len(accounts) == 1:
        return str(accounts[0]["accountSeq"])

    choices = ", ".join(
        f"accountSeq={account.get('accountSeq')} accountType={account.get('accountType')}"
        for account in accounts
    )
    raise RuntimeError(f"multiple accounts found ({choices}); pass --account explicitly")


def _print_json(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def cmd_accounts(args: argparse.Namespace) -> int:
    settings = _settings(args)
    with TossInvestClient(settings) as client:
        return _print_json(client.accounts())


def cmd_prices(args: argparse.Namespace) -> int:
    settings = _settings(args)
    with TossInvestClient(settings) as client:
        return _print_json(client.prices(args.symbols))


def cmd_holdings(args: argparse.Namespace) -> int:
    settings = _settings(args)
    with TossInvestClient(settings) as client:
        account = _resolve_account(args, client)
        return _print_json(client.holdings(account=account, symbol=args.symbol))


def cmd_orders(args: argparse.Namespace) -> int:
    settings = _settings(args)
    with TossInvestClient(settings) as client:
        account = _resolve_account(args, client)
        return _print_json(client.orders(account=account, status=args.status, symbol=args.symbol))


def cmd_buying_power(args: argparse.Namespace) -> int:
    settings = _settings(args)
    with TossInvestClient(settings) as client:
        account = _resolve_account(args, client)
        return _print_json(client.buying_power(account=account, currency=args.currency))


def cmd_sellable(args: argparse.Namespace) -> int:
    settings = _settings(args)
    with TossInvestClient(settings) as client:
        account = _resolve_account(args, client)
        return _print_json(client.sellable_quantity(account=account, symbol=args.symbol))


def cmd_order(args: argparse.Namespace) -> int:
    settings = _settings(args)
    client_order_id = args.client_order_id
    if args.generate_client_order_id:
        client_order_id = generated_client_order_id()
    draft = OrderDraft(
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        order_amount=args.order_amount,
        price=args.price,
        time_in_force=args.time_in_force,
        client_order_id=client_order_id,
        confirm_high_value_order=args.confirm_high_value_order,
    )
    payload = draft.to_api_payload()
    if not args.execute:
        return _print_json({"dryRun": True, "wouldSubmit": payload})
    _guard_live_order(settings, args.i_understand_real_order, payload)
    with TossInvestClient(settings) as client:
        account = _resolve_account(args, client)
        return _print_json(client.create_order(account=account, payload=payload))


def cmd_cancel(args: argparse.Namespace) -> int:
    settings = _settings(args)
    if not args.execute:
        return _print_json({"dryRun": True, "wouldCancelOrderId": args.order_id})
    _guard_live_order(settings, args.i_understand_real_order, {"orderId": args.order_id})
    with TossInvestClient(settings) as client:
        account = _resolve_account(args, client)
        return _print_json(client.cancel_order(account=account, order_id=args.order_id))


def _guard_live_order(settings: Any, acknowledged: bool, payload: dict[str, object]) -> None:
    if not settings.live_trading_enabled:
        raise RuntimeError("live submission requires TOSSINVEST_TRADING_MODE=live")
    if not acknowledged:
        raise RuntimeError("live submission requires --i-understand-real-order")
    if "clientOrderId" not in payload and "orderId" not in payload:
        raise RuntimeError("live order requires --client-order-id or --generate-client-order-id")


if __name__ == "__main__":
    raise SystemExit(main())
