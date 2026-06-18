from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

SPEC_URL = "https://openapi.tossinvest.com/openapi-docs/latest/openapi.json"
DEFAULT_OUTPUT = Path(".cache/toss-invest-trader/tossinvest-openapi.json")


def fetch_spec(*, url: str = SPEC_URL) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def write_spec(spec: dict[str, Any], *, output: Path = DEFAULT_OUTPUT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def download_spec(*, url: str = SPEC_URL, output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    spec = fetch_spec(url=url)
    write_spec(spec, output=output)
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the canonical Toss Invest OpenAPI JSON.")
    parser.add_argument("--url", default=SPEC_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    spec = download_spec(url=args.url, output=args.output)
    version = spec.get("info", {}).get("version")
    print(f"wrote {args.output} openapi={spec.get('openapi')} version={version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
