"""Where the day's raw signals come from.

`load_signals_for` reads Lane C's provider bundle through `providers.py`, and
falls back to the in-lane stand-in below **only in mock mode**. Since Lane C's
`c/mock-providers` merged (2026-09-07) mock mode reads the real seeded
`/fixtures`; the stand-in now fires only when the bundle cannot be built at all.

Live mode never falls back. A live run quietly reasoning over demo data would
produce real decision cards about merchants the household has never heard of.

**Which clock a run reads by is `resolve_now`, not `datetime.now`.** Lane C's
fixture world is anchored to a fixed reference date, and a window measured from
wall clock falls past the end of it and returns nothing at all. See `resolve_now`
for why an empty result is worse here than an exception.

`_demo_signals` is Lane A's own single-day stand-in and lives here rather than in
`/fixtures`, which belongs to Lane C. The four-week world is `replay.py`, which
is scripted rather than read and is what the autonomy curve is measured over.
"""

from __future__ import annotations

import logging
import os
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


AS_OF_ENV = "QH_AS_OF"
"""Override for the run's reference date, as an ISO 8601 string. The escape hatch
for driving a demo at a chosen moment without re-seeding `/fixtures`."""


class InvalidAsOf(ValueError):
    """`QH_AS_OF` was set to something that is not an ISO 8601 datetime."""


def resolve_now(explicit: datetime | None = None, bundle: Any = None) -> datetime:
    """The moment this run treats as "now", in priority order.

    **This exists because wall-clock time is the wrong clock for a fixture
    world.** Lane C's mock providers are anchored to a fixed reference date
    (`DEFAULT_AS_OF`, 2026-08-26, with the last raw signal three days earlier).
    A `LOOKBACK` window measured from `datetime.now(UTC)` falls entirely after
    that world ends, so every provider returns an empty list — and an empty list
    is not an exception. It reads down the whole stack as a quiet day: no
    findings, no actions, and `WeekResult.autonomy_rate` scoring zero actions as
    a perfect 1.0. The demo would look like a working product having a slow
    morning, which is the most expensive way for this to fail.

    Order, most specific first:

    1. `explicit` — the caller named the moment. The replay does this, giving
       each simulated week its own window.
    2. `bundle.as_of` — the provider bundle's own reference date. Present on
       Lane C's mock bundle, `None` on a live one, whose "now" really is now.
    3. `QH_AS_OF` — an ISO 8601 override, for driving a demo at a chosen moment.
    4. Wall clock.

    Raises:
        InvalidAsOf: `QH_AS_OF` is set but unparseable. Deliberately loud: a
            typo here silently reverts the whole run to wall clock, which is the
            exact failure this function exists to prevent.
    """
    if explicit is not None:
        return _aware(explicit)

    # `getattr` rather than an attribute access: `as_of` landed on `Providers`
    # in Lane C's f80c51a, and the stand-in path passes `bundle=None`.
    as_of = getattr(bundle, "as_of", None)
    if as_of is not None:
        return _aware(as_of)

    override = (os.environ.get(AS_OF_ENV) or "").strip()
    if override:
        try:
            return _aware(datetime.fromisoformat(override))
        except ValueError as exc:
            raise InvalidAsOf(f"{AS_OF_ENV}={override!r} is not an ISO 8601 datetime") from exc

    return datetime.now(UTC)


def _aware(moment: datetime) -> datetime:
    """UTC-assumed if naive. Every provider compares against tz-aware datetimes,
    and a naive one raises `TypeError` inside the comparison, several frames from
    the thing that supplied it."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


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
        now: The moment the run considers "now". Optional — when omitted it is
            resolved by `resolve_now`, which prefers the provider bundle's own
            `as_of` over wall clock. The replay passes a date explicitly so each
            simulated week reads its own window.
        scenario: A registered scenario key. Checked *before* the providers,
            because the A6 replay is simulating four specific weeks — asking a
            live provider for them would be asking for data that does not exist.
    """
    resolved = resolve_mode(mode)

    # A scripted scenario is a self-contained world with its own dates, so its
    # clock is resolved **without** the bundle -- and the check stays ahead of
    # `get_providers` so that a scripted run never asks a live provider for four
    # weeks that do not exist.
    scripted = signals_for(scenario, household_id, resolve_now(now))
    if scripted is not None:
        return scripted

    bundle = get_providers(resolved)  # raises in live mode if Lane C is absent
    now = resolve_now(now, bundle)

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
