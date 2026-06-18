# Contributing

This project is intentionally conservative because it can submit real securities orders.

## Development checks

Run before opening a pull request:

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

If the upstream Toss OpenAPI spec changed:

```bash
uv run python scripts/update_openapi_spec.py
uv run pytest -m contract_live
```

When an OpenAPI diff affects a used endpoint, request schema, auth flow, or account header, update the client and tests in the same change.

## Safety rules

- Do not commit credentials, `.env`, account data, order IDs from real accounts, or full account numbers.
- Keep local `.env` permissions restricted, for example `chmod 600 .env`.
- Do not make order commands live by default.
- Do not remove the live-order confirmation gates without equivalent tests and a clear rationale.
- Prefer small, reviewable changes over broad automation.
