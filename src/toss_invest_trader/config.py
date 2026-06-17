from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://openapi.tossinvest.com"


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    base_url: str = DEFAULT_BASE_URL
    trading_mode: str = "paper"

    @property
    def live_trading_enabled(self) -> bool:
        return self.trading_mode == "live"


def load_settings(env_file: str | Path | None = None) -> Settings:
    if env_file is not None:
        load_dotenv(env_file)
    else:
        load_dotenv()

    client_id = os.environ.get("TOSSINVEST_CLIENT_ID", "").strip()
    client_secret = os.environ.get("TOSSINVEST_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "TOSSINVEST_CLIENT_ID and TOSSINVEST_CLIENT_SECRET are required. "
            "Create a server-local .env from .env.example."
        )

    trading_mode = os.environ.get("TOSSINVEST_TRADING_MODE", "paper").strip().lower()
    if trading_mode not in {"paper", "live"}:
        raise RuntimeError("TOSSINVEST_TRADING_MODE must be either 'paper' or 'live'.")

    return Settings(
        client_id=client_id,
        client_secret=client_secret,
        base_url=os.environ.get("TOSSINVEST_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        trading_mode=trading_mode,
    )
