from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/update_openapi_spec.py")
pytestmark = pytest.mark.contract_live


def download_spec() -> dict:
    spec = importlib.util.spec_from_file_location("update_openapi_spec", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fetch_spec()


@cache
def load_spec() -> dict:
    return download_spec()


def test_openapi_snapshot_is_present() -> None:
    spec = load_spec()

    assert spec["openapi"] == "3.1.0"
    assert spec["info"]["title"] == "토스증권 Open API"
    assert spec["servers"] == [{"url": "https://openapi.tossinvest.com"}]


def test_auth_contract_matches_client_credentials_flow() -> None:
    spec = load_spec()
    token = spec["paths"]["/oauth2/token"]["post"]
    request_schema = spec["components"]["schemas"]["OAuth2TokenRequest"]

    assert token["security"] == []
    assert "application/x-www-form-urlencoded" in token["requestBody"]["content"]
    assert request_schema["required"] == ["grant_type", "client_id", "client_secret"]
    assert request_schema["properties"]["grant_type"]["enum"] == ["client_credentials"]


def test_account_header_contract_matches_runtime_resolution() -> None:
    spec = load_spec()
    account_header = spec["components"]["parameters"]["AccountSeq"]

    assert account_header["name"] == "X-Tossinvest-Account"
    assert account_header["in"] == "header"
    assert account_header["required"] is True
    assert account_header["schema"]["type"] == "integer"


def test_order_create_contract_matches_local_order_validation() -> None:
    spec = load_spec()
    schema = spec["components"]["schemas"]["OrderCreateRequest"]
    quantity_based, amount_based = schema["oneOf"]

    assert quantity_based["required"] == ["symbol", "side", "orderType", "quantity"]
    assert quantity_based["properties"]["quantity"]["pattern"] == "^\\d+$"
    assert quantity_based["properties"]["price"]["pattern"] == "^\\d+(\\.\\d+)?$"
    assert quantity_based["properties"]["clientOrderId"]["pattern"] == r"^[a-zA-Z0-9\-_]+$"
    assert quantity_based["properties"]["clientOrderId"]["maxLength"] == 36

    assert amount_based["required"] == ["symbol", "side", "orderType", "orderAmount"]
    assert amount_based["properties"]["orderType"]["enum"] == ["MARKET"]
    assert amount_based["properties"]["orderAmount"]["pattern"] == "^\\d+(\\.\\d+)?$"


def test_client_supported_endpoints_exist_in_openapi_snapshot() -> None:
    spec = load_spec()
    paths = spec["paths"]

    expected = {
        "/oauth2/token": {"post"},
        "/api/v1/accounts": {"get"},
        "/api/v1/prices": {"get"},
        "/api/v1/holdings": {"get"},
        "/api/v1/orders": {"get", "post"},
        "/api/v1/orders/{orderId}/cancel": {"post"},
        "/api/v1/buying-power": {"get"},
        "/api/v1/sellable-quantity": {"get"},
    }
    for path, methods in expected.items():
        assert path in paths
        assert methods.issubset(paths[path].keys())
