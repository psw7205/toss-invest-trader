# Toss Invest OpenAPI snapshot

`tosstrader` can download a local cached copy of the canonical Toss Securities OpenAPI JSON so development can verify API assumptions against a concrete contract, not only prose docs.

The generated JSON file is intentionally ignored by git. It is provided by Toss Securities and is not covered by this project's MIT license.

Source: `https://openapi.tossinvest.com/openapi-docs/latest/openapi.json`

Update the snapshot:

```bash
uv run python scripts/update_openapi_spec.py
```

Run contract checks:

```bash
uv run python scripts/update_openapi_spec.py
uv run pytest -m contract_live
```

If the JSON changes, update client code/tests in the same commit when the change affects an endpoint, schema, auth field, or account header used by this project.
