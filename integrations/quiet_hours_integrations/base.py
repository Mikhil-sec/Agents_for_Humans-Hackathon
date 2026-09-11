"""Provider interfaces — the boundary between the agent and the outside world.

**This file is a contract with Lane A.** Lane A codes against these Protocols from
day one and cannot absorb surprise changes. Treat edits here with the same care as
`/contracts`: announce in `docs/status/DECISIONS.md` first.

Every provider has two implementations:

* `mock/`  reads from `/fixtures`. No credentials. **Must always work.**
* `live/`  real APIs. Requires credentials. Degrades to skipped tests without them.

Safety rules baked into these signatures, not left to discipline:

* `EmailProvider` has `create_draft`. **There is no `send`.** The absence of the
  method is the guarantee — an agent cannot call what does not exist.
* `PaymentProvider` has `schedule_payment`, which creates a *request* a human
  confirms out of band. There is no unattended transfer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from quiet_hours_contracts import Money, ProviderMode, Signal


@runtime_checkable
class EmailProvider(Protocol):
    """Read the inbox and prepare (never send) outbound mail."""

    def fetch_since(self, household_id: str, since: datetime, limit: int = 200) -> list[Signal]:
        """Return email signals newer than `since`, oldest first."""
        ...

    def create_draft(
        self,
        household_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> str:
        """Create a draft and return its provider-side id.

        **This never sends.** There is deliberately no send method on this
        interface — see the module docstring. Do not add one.
        """
        ...

    def get_thread(self, household_id: str, thread_ref: str) -> list[Signal]:
        """Full thread for context, oldest first."""
        ...


@runtime_checkable
class TransactionProvider(Protocol):
    """Read card and bank activity."""

    def fetch_since(self, household_id: str, since: datetime, limit: int = 500) -> list[Signal]:
        """Return transaction signals newer than `since`, oldest first."""
        ...

    def merchant_history(
        self, household_id: str, merchant: str, months: int = 12
    ) -> list[Signal]:
        """Prior charges from one merchant.

        This is what lets BillAnalyst answer "is this normal?" — it is the
        difference between an agent that flags every bill and one that only flags
        the surprising ones.
        """
        ...


@runtime_checkable
class CalendarProvider(Protocol):
    """Read the calendar and add events or reminders."""

    def fetch_between(self, household_id: str, start: datetime, end: datetime) -> list[Signal]:
        ...

    def find_free_slots(
        self, household_id: str, start: datetime, end: datetime, duration_minutes: int
    ) -> list[tuple[datetime, datetime]]:
        """Free windows in the range, earliest first."""
        ...

    def create_event(
        self,
        household_id: str,
        title: str,
        start: datetime,
        end: datetime,
        notes: str | None = None,
    ) -> str:
        """Create an event and return its id. Reversible, so `NOTIFY` risk."""
        ...


@runtime_checkable
class PaymentProvider(Protocol):
    """Prepare payments. Never moves money unattended."""

    def schedule_payment(
        self,
        household_id: str,
        payee: str,
        amount: Money,
        due_at: datetime,
        reference: str | None = None,
    ) -> str:
        """Create a *scheduled payment request* and return its id.

        This produces something a human confirms out of band. There is no method
        on this interface that transfers money without a human in the loop, and
        none may be added.
        """
        ...

    def cancel_scheduled_payment(self, household_id: str, payment_id: str) -> bool:
        ...


@runtime_checkable
class SubscriptionProvider(Protocol):
    """Act on recurring services.

    In mock mode these mutate fixture state. In live mode they are driven by the
    Playwright MCP server against the merchant's own cancellation flow, or fall
    back to drafting a cancellation email through `EmailProvider.create_draft`.
    """

    def cancel(self, household_id: str, merchant: str, note: str | None = None) -> str:
        """Returns a receipt id. Always `CONFIRM` risk or stricter."""
        ...

    def downgrade(self, household_id: str, merchant: str, target_plan: str) -> str:
        ...


class Providers:
    """The bundle handed to the agent. Lane A receives one of these and nothing else.

    Keeping every external dependency behind one object is what makes mock mode a
    single switch rather than a scattering of conditionals.
    """

    def __init__(
        self,
        mode: ProviderMode,
        email: EmailProvider,
        transactions: TransactionProvider,
        calendar: CalendarProvider,
        payments: PaymentProvider,
        subscriptions: SubscriptionProvider,
        *,
        as_of: datetime | None = None,
    ) -> None:
        self.mode = mode
        self.email = email
        self.transactions = transactions
        self.calendar = calendar
        self.payments = payments
        self.subscriptions = subscriptions
        self.as_of = as_of
        """The fixture world's reference "now", or `None` for wall-clock time.

        Every provider method below still takes its own `since`/`start`/`end` —
        this is not a substitute for those. It exists because a *caller*
        computing a lookback window (e.g. "read since 24 hours ago") needs to
        know what "now" means for the bundle it holds. Mock mode is anchored to
        a fixed point in time (see `mock._fixtures.DEFAULT_AS_OF`) so the same
        fixtures read the same way regardless of when the demo runs; live mode
        has no such anchor, because a live run's "now" is simply now.

        `None` means "use wall-clock `datetime.now(UTC)`" — correct for `LIVE`,
        which leaves this unset. `build_mock_providers` always sets it to the
        real reference date. A caller computing a window writes
        `bundle.as_of or datetime.now(UTC)`, never `datetime.now(UTC)` alone —
        the latter is what silently made every mock-mode lookback window read
        as a quiet day once the fixtures' fixed dates fell far enough behind
        wall-clock time.
        """

    @property
    def is_live(self) -> bool:
        return self.mode is ProviderMode.LIVE
