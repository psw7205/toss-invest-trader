# Toss Securities Open API notes

Source of truth: `https://developers.tossinvest.com/llms.txt` → OpenAPI JSON `https://openapi.tossinvest.com/openapi-docs/latest/openapi.json`.

Observed OpenAPI version during bootstrap: `1.1.1`.

Base server: `https://openapi.tossinvest.com`.

Auth:

- `POST /oauth2/token`
- OAuth 2.0 Client Credentials Grant
- Form body: `grant_type=client_credentials`, `client_id`, `client_secret`
- The token response is OAuth-standard, not wrapped in the common API envelope.

Account-scoped APIs require both:

- `Authorization: Bearer <access_token>`
- `X-Tossinvest-Account: <accountSeq>`

Endpoint groups initially wired in this project:

- `GET /api/v1/accounts`
- `GET /api/v1/prices?symbols=...`
- `GET /api/v1/holdings`
- `GET /api/v1/orders?status=OPEN|CLOSED`
- `POST /api/v1/orders`
- `POST /api/v1/orders/{orderId}/cancel`
- `GET /api/v1/buying-power?currency=KRW|USD`
- `GET /api/v1/sellable-quantity?symbol=...`

Trading safety choices in this project:

1. Default mode is `paper`: order commands print the payload and do not call `POST /api/v1/orders`.
2. `accountSeq` is resolved at runtime from `GET /api/v1/accounts`; if exactly one account exists it is auto-selected, otherwise pass `--account`.
3. Live submission requires all of:
   - `TOSSINVEST_TRADING_MODE=live`
   - `--execute`
   - `--i-understand-real-order`
4. `clientOrderId` is required for live orders unless `--generate-client-order-id` is used.
5. Secrets are intentionally absent. Fill `.env` directly on the server.
6. OpenAPI JSON is cached locally in `.cache/toss-invest-trader/tossinvest-openapi.json`; update with `uv run python scripts/update_openapi_spec.py` and verify contract tests when upstream changes.
