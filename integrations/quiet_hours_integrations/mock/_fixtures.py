"""Loading for the raw fixture files under `/fixtures`.

Every mock provider reads through this module rather than opening files itself,
so the five raw shapes — `household.json`, `inbox/*.json`, `transactions.json`,
`calendar.json`, `merchant_history.json` — are parsed and converted to `Signal`
in exactly one place. See `fixtures/README.md` for the documented shape of each
file.

Loading is lazy and un-cached: a provider only fails when a caller actually asks
for the data a missing file would hold, and the exact file or directory that is
missing is always named in the error. Lane C's seeder (`c/fixtures-full`) writes
these files; until it does, `FixturesNotFoundError` is the expected, clean
failure mode, and Lane A's `providers.py` already treats a mock-mode failure as
"fall back to the in-lane stand-in" rather than a crash.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quiet_hours_contracts import Household, Money, Signal, SignalKind


class FixturesNotFoundError(FileNotFoundError):
    """A raw fixture file or directory the mock providers need is not there yet."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"Missing mock fixture at {path}. Generate the fixture set with "
            "`python -m quiet_hours_integrations.mock.seed --out fixtures/`, or add it "
            "by hand following the shape documented in fixtures/README.md."
        )
        self.path = path


class UnknownHouseholdError(ValueError):
    """A caller asked about a household the mock fixtures do not cover."""


def new_id(prefix: str) -> str:
    """Opaque id, uuid4-based. Consumers must not parse these — see `contracts`."""
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FixturesNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_dir(dir_path: Path) -> list[Any]:
    """Every `*.json` file in `dir_path`, parsed, in filename order."""
    if not dir_path.is_dir():
        raise FixturesNotFoundError(dir_path)
    files = sorted(dir_path.glob("*.json"))
    if not files:
        raise FixturesNotFoundError(dir_path / "*.json")
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def load_household(fixtures_dir: Path) -> Household:
    return Household.model_validate(load_json(fixtures_dir / "household.json"))


def require_household(fixtures_dir: Path, household_id: str) -> Household:
    """Load the demo household and confirm the caller means it.

    The mock fixtures cover exactly one household. A mismatched id is almost
    always a bug in the caller, not a real multi-tenant lookup, so this fails
    loudly rather than returning an empty result.
    """
    household = load_household(fixtures_dir)
    if household.household_id != household_id:
        raise UnknownHouseholdError(
            f"{household_id!r} is not the demo household ({household.household_id!r}); "
            "the mock fixtures cover exactly one household."
        )
    return household


def parse_dt(value: str) -> datetime:
    """ISO 8601, including a trailing `Z` — supported by `fromisoformat` since 3.11."""
    return datetime.fromisoformat(value)


def money_from(raw: dict[str, Any] | None) -> Money | None:
    return Money.model_validate(raw) if raw else None


def require_fixture_set(fixtures_dir: Path) -> None:
    """Confirm every raw fixture file the mock providers read is present.

    Called once, eagerly, by `build_mock_providers` — not by each provider —
    so a missing fixture set fails the same way `get_providers(MOCK)` already
    did before any provider existed: it raises, and Lane A's `providers.py`
    catches that and falls back to its in-lane stand-in. Without this gate,
    bundle construction would succeed on a half-empty `/fixtures` and every
    individual read would fail instead, which reads to Lane A as "the
    household genuinely has nothing going on" rather than "the fixtures
    aren't here yet" — a demo that looks quiet rather than one that looks
    broken. See `docs/status/PROGRESS_C.md`, 2026-08-26 entry.
    """
    load_json(fixtures_dir / "household.json")
    load_json_dir(fixtures_dir / "inbox")
    load_json(fixtures_dir / "transactions.json")
    load_json(fixtures_dir / "calendar.json")
    load_json(fixtures_dir / "merchant_history.json")


def signal_from_raw(
    raw: dict[str, Any],
    *,
    household_id: str,
    kind: SignalKind,
    default_source: str,
) -> Signal:
    """One fixture record — an inbox email, a transaction, a calendar entry, or a
    merchant-history entry — as a `Signal`. All four raw shapes share the same
    core fields (`signal_id`, `occurred_at`, `subject`/`body`, `merchant`,
    `amount`), so one converter covers them; `ingested_at` is set to the moment
    of the read, since ingestion happens now even though the event itself is
    historical.
    """
    return Signal(
        signal_id=raw["signal_id"],
        household_id=household_id,
        kind=kind,
        occurred_at=parse_dt(raw["occurred_at"]),
        ingested_at=datetime.now(UTC),
        source=raw.get("source", default_source),
        subject=raw.get("subject"),
        body=raw.get("body"),
        merchant=raw.get("merchant"),
        amount=money_from(raw.get("amount")),
        raw=raw,
    )
