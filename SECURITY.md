# Security Policy

## Scope

This repository contains a client/CLI that can submit real securities orders when configured for live trading. Treat bugs that can leak credentials, bypass live-order safety gates, submit unintended orders, or expose account/order data as security-sensitive.

## Reporting

Please do not open a public issue for vulnerabilities or credential exposure.

Report privately through a direct, non-public channel to the project owner.

## Credential handling

- Never commit `.env` files or real Toss Securities credentials.
- `TOSSINVEST_CLIENT_ID` and `TOSSINVEST_CLIENT_SECRET` must stay server-local.
- Keep server-local `.env` files readable only by the runtime user, for example `chmod 600 .env`.
- Rotate credentials immediately if they are printed in logs, committed, or shared outside the intended server.

## Trading safety

Live order submission intentionally requires all of:

1. `TOSSINVEST_TRADING_MODE=live`
2. `--execute`
3. `--i-understand-real-order`
4. `--client-order-id` or `--generate-client-order-id`

Do not remove or weaken these gates without adding an equivalent safety mechanism and tests.
