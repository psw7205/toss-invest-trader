from __future__ import annotations

import pytest

from toss_invest_trader.config import DEFAULT_BASE_URL, load_settings


def test_env_file_overrides_ambient_trading_mode(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "TOSSINVEST_CLIENT_ID=file-client",
                "TOSSINVEST_CLIENT_SECRET=file-secret",
                "TOSSINVEST_TRADING_MODE=paper",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TOSSINVEST_TRADING_MODE", "live")

    settings = load_settings(env_file)

    assert settings.client_id == "file-client"
    assert settings.client_secret == "file-secret"
    assert settings.trading_mode == "paper"


def test_custom_base_url_requires_explicit_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOSSINVEST_CLIENT_ID", "cid")
    monkeypatch.setenv("TOSSINVEST_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TOSSINVEST_BASE_URL", "https://example.test")
    monkeypatch.delenv("TOSSINVEST_ALLOW_CUSTOM_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="TOSSINVEST_ALLOW_CUSTOM_BASE_URL=1"):
        load_settings()


def test_custom_base_url_can_be_explicitly_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOSSINVEST_CLIENT_ID", "cid")
    monkeypatch.setenv("TOSSINVEST_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TOSSINVEST_BASE_URL", "https://example.test")
    monkeypatch.setenv("TOSSINVEST_ALLOW_CUSTOM_BASE_URL", "1")

    settings = load_settings()

    assert settings.base_url == "https://example.test"
    assert settings.base_url != DEFAULT_BASE_URL
