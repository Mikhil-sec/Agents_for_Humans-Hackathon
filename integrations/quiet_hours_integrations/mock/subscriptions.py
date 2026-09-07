"""Mock `SubscriptionProvider` — an in-memory ledger of cancellations and
downgrades this session performed.

Like payments, there is no dedicated fixture file: the receipt only exists
because this run acted. `household.json` is still consulted for the same reason
as every other mock provider.
"""

from __future__ import annotations

from pathlib import Path

from ._fixtures import new_id, require_household


class MockSubscriptionProvider:
    """Satisfies `quiet_hours_integrations.base.SubscriptionProvider`."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir
        self.cancelled: list[dict] = []
        self.downgraded: list[dict] = []

    def cancel(self, household_id: str, merchant: str, note: str | None = None) -> str:
        require_household(self._fixtures_dir, household_id)
        receipt_id = new_id("rcpt")
        self.cancelled.append(
            {
                "receipt_id": receipt_id,
                "household_id": household_id,
                "merchant": merchant,
                "note": note,
            }
        )
        return receipt_id

    def downgrade(self, household_id: str, merchant: str, target_plan: str) -> str:
        require_household(self._fixtures_dir, household_id)
        receipt_id = new_id("rcpt")
        self.downgraded.append(
            {
                "receipt_id": receipt_id,
                "household_id": household_id,
                "merchant": merchant,
                "target_plan": target_plan,
            }
        )
        return receipt_id
