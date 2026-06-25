# toss-invest-trader

토스증권 Open API 기반의 매매 client/CLI입니다. 실제 주문이 가능한 도구이므로 기본은 dry-run이며, live 주문에는 명시적인 안전장치를 둡니다.

## 원칙

- 기본은 `paper` mode입니다. 주문 명령은 기본적으로 API를 호출하지 않고 payload만 출력합니다.
- 실제 주문은 세 겹의 명시적 확인이 있어야만 나갑니다.
  1. 서버 `.env`의 `TOSSINVEST_TRADING_MODE=live`
  2. CLI의 `--execute`
  3. CLI의 `--i-understand-real-order`
- 실제 주문은 `clientOrderId`를 요구합니다. 직접 `--client-order-id`를 주거나 `--generate-client-order-id`를 쓰세요.
- 인증 정보는 커밋하지 않습니다. 서버에서 `.env.example`을 `.env`로 복사한 뒤 직접 입력하세요.
- `accountSeq`는 환경변수로 고정하지 않습니다. 계좌가 1개면 API에서 자동 선택하고, 여러 개면 `--account`로 명시합니다.
- API 정합성은 로컬에서 내려받은 Toss OpenAPI JSON 기준으로 확인합니다. 생성된 JSON은 커밋하지 않습니다.
- 현재는 전체 OpenAPI wrapper가 아니라 계좌/시세/주문 조회 일부와 주문 생성/취소를 제공하는 작은 client입니다.

## Setup

```bash
uv sync --group dev
cp .env.example .env
chmod 600 .env
# edit .env on the server
```

필수 환경변수:

- `TOSSINVEST_CLIENT_ID`
- `TOSSINVEST_CLIENT_SECRET`

선택 환경변수:

- `TOSSINVEST_TRADING_MODE`: `paper` 또는 `live`; 기본 `paper`
- `TOSSINVEST_BASE_URL`: 기본 `https://openapi.tossinvest.com`

## Supported endpoints

`TossInvestClient`는 현재 다음 Toss Open API endpoint를 감쌉니다.

| Method | Path | CLI |
| --- | --- | --- |
| `POST` | `/oauth2/token` | internal |
| `GET` | `/api/v1/accounts` | `accounts` |
| `GET` | `/api/v1/prices` | `prices` |
| `GET` | `/api/v1/prices` | `quote` |
| `GET` | `/api/v1/candles` | `candles` |
| `GET` | `/api/v1/price-limits` | `price-limits` |
| `GET` | `/api/v1/market-calendar/KR` | `market-calendar KR` |
| `GET` | `/api/v1/market-calendar/US` | `market-calendar US` |
| `GET` | `/api/v1/holdings` | `holdings` |
| `GET` | `/api/v1/orders` | `orders` |
| `POST` | `/api/v1/orders` | `order --execute` |
| `POST` | `/api/v1/orders/{orderId}/cancel` | `cancel --execute` |
| `GET` | `/api/v1/buying-power` | `buying-power` |
| `GET` | `/api/v1/sellable-quantity` | `sellable` |

다른 endpoint는 아직 의도적으로 감싸지 않습니다. 매매에 영향을 줄 수 있는 endpoint를 추가할 때는 OpenAPI contract test와 CLI 안전장치 검토를 함께 진행합니다.

## Account resolution

계좌/자산/주문 API는 Toss 문서상 `X-Tossinvest-Account` 헤더가 필요합니다. 이 값은 `.env`에 저장하지 않고 `GET /api/v1/accounts` 응답의 `accountSeq`에서 결정합니다.

CLI 동작:

1. `--account`를 넘기면 그 값을 사용합니다.
2. `--account`가 없으면 `GET /api/v1/accounts`를 호출합니다.
3. 계좌가 정확히 1개면 자동 선택합니다.
4. 계좌가 0개 또는 2개 이상이면 중단하고 `--account` 명시를 요구합니다.

## Read-only commands

```bash
uv run tosstrader accounts
uv run tosstrader prices 005930 AAPL
uv run tosstrader quote AAPL
uv run tosstrader candles AAPL --interval 1d --count 100
uv run tosstrader candles AAPL --interval 1m --count 50 --raw
uv run tosstrader price-limits AAPL
uv run tosstrader market-calendar US --date 2026-01-02
uv run tosstrader holdings
uv run tosstrader orders --status OPEN --from-date 2026-01-01 --to-date 2026-01-31
uv run tosstrader buying-power --currency KRW
uv run tosstrader sellable --symbol AAPL
```

다계좌일 때는 명시합니다.

```bash
uv run tosstrader holdings --account 1
```

## Dry-run order

```bash
uv run tosstrader order \
  --symbol AAPL \
  --side BUY \
  --order-type LIMIT \
  --quantity 1 \
  --price 180.00 \
  --client-order-id manual-aapl-001
```

## Live order

`.env`에서 먼저:

```dotenv
TOSSINVEST_TRADING_MODE=live
```

그 다음 명시적으로 실행:

```bash
uv run tosstrader order \
  --symbol AAPL \
  --side BUY \
  --order-type LIMIT \
  --quantity 1 \
  --price 180.00 \
  --client-order-id manual-aapl-001 \
  --execute \
  --i-understand-real-order
```

취소도 동일하게 dry-run 기본입니다.

```bash
uv run tosstrader cancel <order-id>
uv run tosstrader cancel <order-id> --execute --i-understand-real-order
```

Dry-run order/cancel output includes operation metadata, target endpoint/method, execution mode,
preflight checks, and the payload or order ID that would be submitted. Dry-run does not load
credentials or create an HTTP client.

## Python API

```python
from toss_invest_trader import OrderDraft, TossInvestClient, load_settings

settings = load_settings()
with TossInvestClient(settings) as client:
    quote = client.quote("AAPL")
    candles = client.candles("AAPL", "1d", count=100)
    orders = client.orders(
        account="1",
        status="OPEN",
        symbol="AAPL",
        from_date="2026-01-01",
        to_date="2026-01-31",
        limit=50,
    )

draft = OrderDraft(
    symbol="AAPL",
    side="BUY",
    order_type="LIMIT",
    quantity="1",
    price="180.00",
    client_order_id="manual-aapl-001",
)
payload = draft.to_api_payload()
```

## OpenAPI contract check

Toss OpenAPI JSON은 수동 refresh 때만 `.cache/`에 내려받고 커밋하지 않습니다.

```bash
uv run python scripts/update_openapi_spec.py
uv run pytest -m contract_live
```

`tests/test_openapi_contract.py`는 live OpenAPI 문서를 메모리로 내려받아 검증하고, repo에 JSON을 쓰지 않습니다. 기본 `uv run pytest`에서는 외부 네트워크가 필요한 contract test를 제외합니다. 스펙 변경으로 contract test가 실패하면 이 프로젝트가 쓰는 endpoint/schema/auth/account header에 영향이 있는지 확인하고 client/test를 함께 갱신합니다.

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run tosstrader --help
```

API 조사 메모는 `docs/api-notes.md`에 있습니다.
