"""Where the day's raw signals come from.

**This is a temporary in-lane stand-in.** The real source is Lane C's provider
bundle (`integrations.get_providers()`), which still raises `NotImplementedError`
as of 2026-08-23 — that is A4, and it is the reason this file exists rather than
the graph importing `/integrations` directly.

Keeping the seam here rather than inside `graph.py` means A4 is a one-function
swap: `load_signals` starts calling providers and nothing else in the lane moves.
The graph already treats signals as opaque contract objects.

The fixture below is Lane A's own, deliberately small, and lives here rather than
in `/fixtures` because that directory belongs to Lane C. When Yorvan's four-week
fixtures land, this is deleted, not merged with them.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from quiet_hours_contracts import Money, Signal, SignalKind


def _demo_signals(household_id: str, now: datetime) -> list[Signal]:
    """A day's worth of household admin, chosen to exercise every specialist.

    One routine bill (triage should say `nothing_to_do` and stay quiet), one
    unused subscription (the money decision that interrupts), one trial about to
    convert, and one appointment needing a reply.
    """
    return [
        Signal(
            signal_id="sig_gas_bill",
            household_id=household_id,
            kind=SignalKind.EMAIL,
            occurred_at=now - timedelta(hours=6),
            ingested_at=now,
            source="mock_gmail",
            subject="Your British Gas bill is ready",
            body=(
                "Your bill for this month is GBP 84.20, due on the 28th. "
                "Last month you paid GBP 83.10."
            ),
            merchant="British Gas",
            amount=Money(amount_minor=8420, currency="GBP"),
        ),
        Signal(
            signal_id="sig_fitlife_charge",
            household_id=household_id,
            kind=SignalKind.TRANSACTION,
            occurred_at=now - timedelta(days=1),
            ingested_at=now,
            source="mock_bank",
            subject="FITLIFE GYM MEMBERSHIP",
            body=(
                "Monthly charge of GBP 38.00. No visit recorded against this "
                "membership in the last 90 days."
            ),
            merchant="FitLife",
            amount=Money(amount_minor=3800, currency="GBP"),
        ),
        Signal(
            signal_id="sig_streamly_trial",
            household_id=household_id,
            kind=SignalKind.EMAIL,
            occurred_at=now - timedelta(hours=20),
            ingested_at=now,
            source="mock_gmail",
            subject="Your Streamly free trial ends in 3 days",
            body=(
                "After 3 days you will be charged GBP 12.99 a month unless you "
                "cancel before then."
            ),
            merchant="Streamly",
            amount=Money(amount_minor=1299, currency="GBP"),
        ),
        Signal(
            signal_id="sig_dentist_appt",
            household_id=household_id,
            kind=SignalKind.CALENDAR_EVENT,
            occurred_at=now + timedelta(days=9),
            ingested_at=now,
            source="mock_calendar",
            subject="Dental check-up — please confirm",
            body=(
                "Your appointment is on the 2nd at 09:15. The practice asks you "
                "to confirm at least 48 hours in advance."
            ),
            merchant="Bridge Street Dental",
        ),
    ]


def load_signals_for(household_id: str, *, mode: str | None = None) -> list[Signal]:
    """The day's signals for one household.

    Args:
        household_id: Whose signals to load.
        mode: `mock` or `live`. Defaults to `QH_PROVIDER_MODE`, then `mock`.
    """
    resolved = (mode or os.environ.get("QH_PROVIDER_MODE") or "mock").strip().casefold()

    if resolved == "live":
        # A4. Deliberately a hard failure rather than a silent fall back to the
        # fixture: a live run quietly reasoning over demo data would produce real
        # decision cards about merchants the household has never heard of.
        raise NotImplementedError(
            "Live signal ingestion needs Lane C's get_providers() (A4). "
            "Run with QH_PROVIDER_MODE=mock until it lands."
        )

    return _demo_signals(household_id, datetime.now(UTC))


def render_signals(signals: list[Signal]) -> str:
    """Signals as compact text for a model's context.

    One line per signal, `signal_id` first because every downstream node is
    required to cite it as evidence — if the id is hard to see, the citation gets
    invented, and an invented citation is worse than no finding at all.
    """
    if not signals:
        return "No signals arrived today."

    lines = []
    for signal in signals:
        amount = f" | {signal.amount}" if signal.amount else ""
        merchant = f" | {signal.merchant}" if signal.merchant else ""
        lines.append(
            f"- [{signal.signal_id}] ({signal.kind.value}, {signal.source}){merchant}{amount}\n"
            f"    {signal.subject or ''}\n"
            f"    {signal.body or ''}"
        )
    return "\n".join(lines)
