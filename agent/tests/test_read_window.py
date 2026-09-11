"""The run's read window: its far edge, and the four windows the replay tiles.

Lane C's `EmailProvider.fetch_since` and `TransactionProvider.fetch_since` take
a `since` and no `until`, so a read is open-ended — asking the seeded world for
week 1 returns week 1 *and every week after it*. Lane C ruled on 11 September
that `as_of` is a **day**, and that Lane A therefore applies the far edge itself
rather than widening a frozen Protocol on freeze eve. These tests pin that
ruling, because it is the kind of decision that gets quietly undone by someone
later "tidying up" a filter they do not recognise.

Two properties matter and both are checked against Lane C's real fixtures rather
than a fake, because the thing worth knowing is whether the windows fit *that*
world:

* **The far edge is end-of-day, not the instant.** Lane C dated two signals into
  the hours after midnight on the reference date so that a judge opening the
  demo finds a card waiting. A strict `<= now` drops them.
* **The four windows partition the world.** Every signal in exactly one week —
  a signal read twice inflates the denominator of the week that re-reads it and
  deflates its autonomy rate with work an earlier week already did.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from quiet_hours_contracts import Money, Signal, SignalKind

from quiet_hours_agent import providers as providers_module
from quiet_hours_agent.replay import FixtureWorldUnavailable, fixture_weeks
from quiet_hours_agent.signals import end_of_day, load_signals_for

HOUSEHOLD = "hh_demo"


@pytest.fixture(autouse=True)
def clean_cache():
    providers_module.reset_cache()
    yield
    providers_module.reset_cache()


@pytest.fixture
def weeks():
    """Lane C's four windows, skipped rather than failed if the world is absent.

    `/fixtures` is committed, so this should never skip in CI. It skips rather
    than errors so that a developer who has deleted their fixture set to test the
    fallback path does not get a wall of unrelated red.
    """
    try:
        return fixture_weeks()
    except FixtureWorldUnavailable as exc:  # pragma: no cover - only without Lane C
        pytest.skip(f"Lane C's seeded world is not available: {exc}")


# --------------------------------------------------------------------------
# The far edge
# --------------------------------------------------------------------------


def test_end_of_day_is_the_last_instant_of_the_same_day():
    assert end_of_day(datetime(2026, 8, 26, 0, 0, tzinfo=UTC)) == datetime(
        2026, 8, 26, 23, 59, 59, 999999, tzinfo=UTC
    )


def test_a_signal_later_the_same_day_survives_the_far_edge(weeks):
    """The whole reason the edge is a day and not an instant.

    `sig_thetimes_reminder` is dated 08:00 on the reference date, eight hours
    after the midnight `as_of`. It is the trigger for the trial-conversion card
    the demo is meant to open on. A `<= now` filter deletes it silently, and the
    inbox a judge sees goes from having something in it to being empty.
    """
    last = weeks[-1]
    ids = {
        signal.signal_id
        for signal in load_signals_for(
            HOUSEHOLD, mode="mock", now=last.when, lookback=last.lookback
        )
    }

    assert "sig_thetimes_reminder" in ids
    assert "sig_fitlife_renewal" in ids


def test_signals_after_the_window_are_not_read(weeks):
    """Week 1 must not come back holding weeks 2, 3 and 4.

    This is the bug the far edge exists for: without it the first window
    returned 61 of the world's 63 signals and no past week could be isolated.
    """
    first = weeks[0]
    signals = load_signals_for(HOUSEHOLD, mode="mock", now=first.when, lookback=first.lookback)

    assert signals, "week 1 must read something, or this proves nothing"
    limit = end_of_day(first.when)
    late = [s.signal_id for s in signals if s.occurred_at > limit]
    assert not late, f"week 1 read signals from later weeks: {late}"


def test_the_far_edge_does_not_clamp_the_calendar(monkeypatch):
    """The calendar is read *forward* and must stay that way.

    An appointment that needs confirming is only actionable while there is still
    time to confirm it, so `CALENDAR_HORIZON` looks a fortnight ahead. Applying
    the retrospective far edge to it would return nothing but the appointments
    it is already too late to move — a silent, total loss of the scheduler's
    input that no other test would notice.
    """
    now = datetime(2026, 8, 26, tzinfo=UTC)
    ahead = now + timedelta(days=3)

    class Bundle:
        as_of = now

        class email:
            @staticmethod
            def fetch_since(household_id, since, limit=200):
                return []

        class transactions:
            @staticmethod
            def fetch_since(household_id, since, limit=500):
                return []

        class calendar:
            @staticmethod
            def fetch_between(household_id, start, end):
                return [
                    Signal(
                        signal_id="sig_future_appt",
                        household_id=HOUSEHOLD,
                        kind=SignalKind.CALENDAR_EVENT,
                        occurred_at=ahead,
                        ingested_at=now,
                        source="calendar",
                        subject="Dental check-up",
                        body="Please confirm.",
                        merchant="Bridge Street Dental",
                        amount=Money(amount_minor=0, currency="GBP"),
                    )
                ]

    monkeypatch.setattr(providers_module, "_build", lambda mode: Bundle())
    providers_module.reset_cache()

    signals = load_signals_for(HOUSEHOLD, mode="mock", now=now)

    assert [s.signal_id for s in signals] == ["sig_future_appt"]


def test_the_calendar_window_starts_where_the_rest_of_the_window_starts(monkeypatch):
    """Anchored at `since`, not at `now`.

    Anchored at `now` the calendar can only ever return the future, so an
    appointment earlier the same day is invisible — and in the replay, where a
    week runs at the end of that week, every appointment the week contained had
    already happened and the calendar came back empty. That silently dropped
    Lane C's `dentist_clash`, a CONFIRM in week 1.
    """
    now = datetime(2026, 8, 26, tzinfo=UTC)
    seen: dict[str, datetime] = {}

    class Bundle:
        as_of = now

        class email:
            @staticmethod
            def fetch_since(household_id, since, limit=200):
                return []

        class transactions:
            @staticmethod
            def fetch_since(household_id, since, limit=500):
                return []

        class calendar:
            @staticmethod
            def fetch_between(household_id, start, end):
                seen["start"] = start
                seen["end"] = end
                return []

    monkeypatch.setattr(providers_module, "_build", lambda mode: Bundle())
    providers_module.reset_cache()

    load_signals_for(HOUSEHOLD, mode="mock", now=now, lookback=timedelta(days=7))

    assert seen["start"] == now - timedelta(days=7)
    assert seen["end"] > now


# --------------------------------------------------------------------------
# The four windows
# --------------------------------------------------------------------------


def test_the_windows_abut_exactly(weeks):
    """Each window starts where the previous one ended.

    A gap drops signals; an overlap counts them twice. Both are invisible in the
    output — the run simply reports a different number — which is why this is
    asserted on the arithmetic rather than left to be noticed.
    """
    assert len(weeks) == 4

    previous = None
    for week in weeks:
        since = week.when - week.lookback
        if previous is not None:
            assert since == previous, f"{week.label} does not abut the previous window"
        previous = end_of_day(week.when)


def test_the_last_window_runs_to_the_reference_date(weeks):
    """Not to week 4's Sunday.

    Lane C dated `sig_fitlife_renewal` and `sig_thetimes_reminder` into the tail
    between the two, deliberately. Ending at the Sunday takes the demo's pending
    card with it.
    """
    from quiet_hours_integrations.mock._fixtures import DEFAULT_AS_OF

    assert weeks[-1].when == DEFAULT_AS_OF


def test_the_four_windows_cover_every_signal_exactly_once(weeks):
    """The property that makes a four-week curve measurable at all."""
    seen: dict[str, list[str]] = {}
    for week in weeks:
        for signal in load_signals_for(
            HOUSEHOLD, mode="mock", now=week.when, lookback=week.lookback
        ):
            seen.setdefault(signal.signal_id, []).append(week.label)

    duplicated = {sid: where for sid, where in seen.items() if len(where) > 1}
    assert not duplicated, f"read in more than one week: {duplicated}"

    # Every signal Lane C seeded, not merely every signal some window happened
    # to return — a window set that covered half the world would pass the
    # no-duplicates check on its own.
    from quiet_hours_integrations.mock._fixtures import DEFAULT_AS_OF

    whole_world = load_signals_for(
        HOUSEHOLD,
        mode="mock",
        now=DEFAULT_AS_OF,
        lookback=DEFAULT_AS_OF - datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert set(seen) == {s.signal_id for s in whole_world}
