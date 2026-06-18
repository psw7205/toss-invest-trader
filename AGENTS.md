# Repository Guidelines

## Project Structure

This is a Python package using the `src` layout. Runtime code lives in
`src/toss_invest_trader/`: `cli.py` exposes the `tosstrader` command,
`client.py` wraps Toss Invest API calls, `models.py` defines order payload
validation, and `config.py` loads environment settings. Tests live in `tests/`
and should mirror behavior by area. Operational examples live in `configs/`,
API notes live in `docs/`, and OpenAPI refresh tooling lives in
`scripts/update_openapi_spec.py`.

## Development Commands

- `uv sync --locked --group dev`: install runtime and development dependencies
  from `uv.lock`.
- `uv run --locked ruff check .`: run lint checks.
- `uv run --locked ruff format --check .`: verify formatting.
- `uv run --locked mypy .`: run static type checks.
- `uv run --locked pytest -m 'not contract_live'`: run the default local test
  suite without network-dependent contract checks.
- `uv run --locked pytest -m contract_live`: fetch the live Toss OpenAPI
  document in memory and validate project assumptions.
- `uv build`: verify source distribution and wheel packaging.
- `uv run --locked tosstrader --help`: smoke-test the CLI entry point.
- `uv run python scripts/update_openapi_spec.py`: cache the Toss OpenAPI JSON
  under `.cache/` for local inspection.

## Coding Style

Use idiomatic Python with clear type-oriented names and 4-space indentation.
Keep modules focused around their current responsibilities: CLI parsing in
`cli.py`, HTTP behavior in `client.py`, request validation in `models.py`, and
environment handling in `config.py`. Ruff enforces a 100-character line length
and the `E`, `F`, `I`, `UP`, `B`, and `SIM` rule groups. Prefer small helpers
over broad abstractions, and keep live-trading safety gates explicit.

## Testing Guidelines

Use `pytest` for tests. Add or update tests when changing CLI behavior, request
payloads, account resolution, OpenAPI assumptions, settings, or trading safety
checks. Default tests must not require real credentials, live accounts, or
network access. Network-dependent OpenAPI drift checks must use the
`contract_live` marker.

## OpenAPI Handling

Do not commit generated Toss OpenAPI JSON. The live contract test should fetch
the external document in memory, and manual refreshes should write only to
ignored cache paths. Keep `docs/openapi/*.json` untracked unless a deliberate
project-owned fixture is introduced with a clear license decision.

## Security Rules

Never commit `.env`, credentials, account identifiers from real accounts, order
IDs, or full account numbers. Keep local `.env` files restricted with
`chmod 600 .env`. Keep `paper` mode as the default. Live order submission must
continue to require `TOSSINVEST_TRADING_MODE=live`, `--execute`, and
`--i-understand-real-order`; live orders must also require `clientOrderId`.
Custom `TOSSINVEST_BASE_URL` must remain opt-in through
`TOSSINVEST_ALLOW_CUSTOM_BASE_URL=1`.

## Commit Guidelines

Use `type(scope): what + where` for commit subjects, for example
`chore(project): harden ci and trading safety`. Stage only files relevant to the
requested scope. Before committing code changes, run the relevant verification
commands and include the commands in the final report.
