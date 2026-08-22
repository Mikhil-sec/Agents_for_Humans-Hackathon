"""The fixtures backend - static, contract-shaped JSON from /fixtures.

This is the reason Lane B never waits for Lane A. Every screen in the web app is
built and demoed against this; when the agent is ready, flip `QH_BACKEND=live`
and, if the contract held, nothing changes.

It is also what a judge gets from `make demo`, so it must stay working.

LANE B: keep this honest. If it serves shapes the live backend cannot produce,
you will discover it on 11 September, which is the worst possible day.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@lru_cache(maxsize=32)
def _load(name: str) -> Any:
    path = FIXTURES / name
    if not path.exists():
        raise FileNotFoundError(
            f"missing fixture {path}. Lane C generates these: "
            "python -m quiet_hours_integrations.mock.seed --out fixtures/"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def pending_decisions() -> list[dict[str, Any]]:
    return [d for d in _load("decisions.json") if d.get("status") == "pending"]


def all_activity() -> list[dict[str, Any]]:
    return _load("activity.json")


def all_policies() -> list[dict[str, Any]]:
    return _load("policies.json")


def all_runs() -> list[dict[str, Any]]:
    return _load("runs.json")
