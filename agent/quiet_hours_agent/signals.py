"""Where the day's raw signals come from.

`load_signals_for` reads Lane C's provider bundle through `providers.py`, and
falls back to the in-lane stand-in below **only in mock mode**. As of 2026-08-24
`get_providers()` still raises `NotImplementedError`, so mock mode is on the
stand-in — but nothing here needs to change when Lane C lands, which is what
finishes A4 on this side.

Live mode never falls back. A live run quietly reasoning over demo data would
produce real decision cards about merchants the household has never heard of.

The fixtures below are Lane A's own and live here rather than in `/fixtures`,
which belongs to Lane C. There are two: one day (`_demo_signals`, what a single
run sees) and four weeks (`replay.py`, what the autonomy curve is measured over).
When Yorvan's fixtures land, these are deleted, not merged with them.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from quiet_hours_contracts import Money, Signal, SignalKind

from .providers import get_providers, resolve_mode
from .scenarios import signals_for

logger = logging.getLogger(__name__)


class SignalSourcesUnavailable(RuntimeError):
    """Every provider in the bundle failed to read. See `_from_providers`."""


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
                "After 3 days you will be charged GBP 12.99 a month unless you cancel before then."
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


LOOKBACK = timedelta(days=1)
"""How far back a daily run reads. One day, because the run is daily and a wider
window re-surfaces signals earlier runs already acted on."""

CALENDAR_HORIZON = timedelta(days=14)
"""How far *forward* the calendar is read. An appointment needing confirmation is
only actionable while there is still time to confirm it."""


def load_signals_for(
    household_id: str,
    *,
    mode: str | None = None,
    now: datetime | None = None,
    scenario: str | None = None,
) -> list[Signal]:
    """The day's signals for one household.

    Reads Lane C's providers when they exist, and Lane A's stand-in when they do
    not — but **only in mock mode**. In live mode a missing provider is a hard
    failure, because a live run quietly reasoning over demo data would produce
    real decision cards about merchants the household has never heard of.

    Args:
        household_id: Whose signals to load.
        mode: `mock` or `live`. Defaults to `QH_PROVIDER_MODE`, then `mock`.
        now: The moment the run considers "now". The replay passes a past date so
            each simulated week reads its own window.
        scenario: A registered scenario key. Checked *before* the providers,
            because the A6 replay is simulating four specific weeks — asking a
            live provider for them would be asking for data that does not exist.
    """
    resolved = resolve_mode(mode)
    now = now or datetime.now(UTC)

    scripted = signals_for(scenario, household_id, now)
    if scripted is not None:
        return scripted

    bundle = get_providers(resolved)  # raises in live mode if Lane C is absent
    if bundle is not None:
        return _from_providers(bundle, household_id, now)

    return _demo_signals(household_id, now)


def _from_providers(bundle: Any, household_id: str, now: datetime) -> list[Signal]:
    """Everything the three read-only providers have, merged and ordered.

    Each provider is read independently and a failure in one does not lose the
    others: an unreachable bank should not stop the agent noticing that a dental
    appointment needs confirming. What it must never do is silently look like a
    quiet day — hence the warning, and hence `sources_failed` being visible to
    the caller through the log rather than swallowed.
    """
    since = now - LOOKBACK
    signals: list[Signal] = []

    sources = (
        ("email", lambda: bundle.email.fetch_since(household_id, since)),
        ("transactions", lambda: bundle.transactions.fetch_since(household_id, since)),
        (
            "calendar",
            lambda: bundle.calendar.fetch_between(household_id, now, now + CALENDAR_HORIZON),
        ),
    )

    failed: list[str] = []
    for label, read in sources:
        try:
            signals.extend(read() or [])
        except Exception:
            failed.append(label)
            logger.warning("could not read %s signals for %s", label, household_id, exc_info=True)

    # **Every source failing is not a quiet day.** One down is tolerable — that is
    # what the per-source catch is for. All three down is a bundle-level fault
    # affecting every provider equally: the wrong `household_id` (Lane C's mock
    # providers raise `UnknownHouseholdError` from `require_household`, which every
    # `fetch_*` calls), a fixtures directory that moved, a bad bundle.
    #
    # Swallowing that returns an empty signal list, which reads all the way down
    # the stack as "nothing happened today": no findings, no actions, and
    # `WeekResult.autonomy_rate` scores zero actions as **1.0**. A caller bug would
    # publish itself as a perfect autonomy score. Fail instead.
    if failed and len(failed) == len(sources):
        raise SignalSourcesUnavailable(
            f"every signal source failed for {household_id!r} ({', '.join(failed)}); "
            "this is a bundle-level fault, not a quiet day — see the logged tracebacks."
        )

    # Oldest first, matching the order every provider promises individually, so
    # the rendered context reads chronologically whatever order they came back in.
    signals.sort(key=lambda signal: signal.occurred_at)
    logger.info("loaded %d signal(s) from Lane C's providers", len(signals))
    return signals


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
