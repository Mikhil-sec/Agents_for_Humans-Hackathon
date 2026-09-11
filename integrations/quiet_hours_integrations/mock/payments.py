"""Mock `PaymentProvider` — an in-memory ledger of scheduled payment requests.

There is no `payments.json` fixture: a scheduled request only exists because an
agent run created one this session, so there is nothing to seed. `household.json`
is still consulted, so a request for an unknown household fails the same way
every other mock provider does.

Matches the safety guarantee in `base.py`: this creates *requests*, never an
unattended transfer, in mock mode or any other.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from quiet_hours_contracts import Money

from ._fixtures import new_id, require_household


class MockPaymentProvider:
    """Satisfies `quiet_hours_integrations.base.PaymentProvider`."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir
        self.scheduled: dict[str, dict] = {}
        """Every live (uncancelled) request, keyed by payment id."""

    def schedule_payment(
        self,
        household_id: str,
        payee: str,
        amount: Money,
        due_at: datetime,
        reference: str | None = None,
    ) -> str:
        require_household(self._fixtures_dir, household_id)
        payment_id = new_id("pay")
        self.scheduled[payment_id] = {
            "household_id": household_id,
            "payee": payee,
            "amount": amount,
            "due_at": due_at,
            "reference": reference,
        }
        return payment_id

    def cancel_scheduled_payment(self, household_id: str, payment_id: str) -> bool:
        require_household(self._fixtures_dir, household_id)
        request = self.scheduled.get(payment_id)
        if request is None or request["household_id"] != household_id:
            return False
        del self.scheduled[payment_id]
        return True
