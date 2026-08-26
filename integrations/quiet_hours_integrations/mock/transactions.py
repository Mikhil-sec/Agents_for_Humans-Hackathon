"""Mock `TransactionProvider` — reads `fixtures/transactions.json` and
`fixtures/merchant_history.json`.

`transactions.json` is a flat list of the four-week window; `merchant_history.json`
is a dict keyed by merchant name, each value a list of the same per-charge shape,
covering twelve months. Both are documented in `fixtures/README.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from quiet_hours_contracts import Signal, SignalKind

from ._fixtures import load_json, require_household, signal_from_raw

DEFAULT_SOURCE = "mock_bank"


class MockTransactionProvider:
    """Satisfies `quiet_hours_integrations.base.TransactionProvider`."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir

    def fetch_since(self, household_id: str, since: datetime, limit: int = 500) -> list[Signal]:
        require_household(self._fixtures_dir, household_id)
        raw_txns: list[dict[str, Any]] = load_json(self._fixtures_dir / "transactions.json")
        signals = [
            signal_from_raw(
                raw,
                household_id=household_id,
                kind=SignalKind.TRANSACTION,
                default_source=DEFAULT_SOURCE,
            )
            for raw in raw_txns
        ]
        signals = [s for s in signals if s.occurred_at > since]
        signals.sort(key=lambda s: s.occurred_at)
        return signals[:limit]

    def merchant_history(
        self, household_id: str, merchant: str, months: int = 12
    ) -> list[Signal]:
        require_household(self._fixtures_dir, household_id)
        history: dict[str, list[dict[str, Any]]] = load_json(
            self._fixtures_dir / "merchant_history.json"
        )
        raw_entries = history.get(merchant, [])
        signals = [
            signal_from_raw(
                raw,
                household_id=household_id,
                kind=SignalKind.TRANSACTION,
                default_source=DEFAULT_SOURCE,
            )
            for raw in raw_entries
        ]
        cutoff = datetime.now(UTC) - timedelta(days=30 * months)
        signals = [s for s in signals if s.occurred_at >= cutoff]
        signals.sort(key=lambda s: s.occurred_at)
        return signals
