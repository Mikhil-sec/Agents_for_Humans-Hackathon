"""Mock providers — read `/fixtures`, satisfy `base.py`'s Protocols, fail clean.

Two concerns per provider: it reads the documented raw shape correctly, and it
fails with a clear `FixturesNotFoundError` (not a bare `FileNotFoundError`
traceback, not a silent empty result) when the file it needs is not there yet —
today's real state for everything except `household.json`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from quiet_hours_contracts import Money

from quiet_hours_integrations.base import (
    CalendarProvider,
    EmailProvider,
    PaymentProvider,
    SubscriptionProvider,
    TransactionProvider,
)
from quiet_hours_integrations.mock._fixtures import (
    FixturesNotFoundError,
    UnknownHouseholdError,
)
from quiet_hours_integrations.mock.calendar import MockCalendarProvider
from quiet_hours_integrations.mock.email import MockEmailProvider
from quiet_hours_integrations.mock.payments import MockPaymentProvider
from quiet_hours_integrations.mock.subscriptions import MockSubscriptionProvider
from quiet_hours_integrations.mock.transactions import MockTransactionProvider

from .conftest import HOUSEHOLD_ID

EPOCH = datetime(2020, 1, 1, tzinfo=UTC)


# --------------------------------------------------------------------------
# Protocol conformance
# --------------------------------------------------------------------------


def test_mock_providers_satisfy_lane_as_protocols(seeded_fixtures_dir: Path):
    """If this fails, a provider drifted from `base.py`'s Protocols."""
    assert isinstance(MockEmailProvider(seeded_fixtures_dir), EmailProvider)
    assert isinstance(MockTransactionProvider(seeded_fixtures_dir), TransactionProvider)
    assert isinstance(MockCalendarProvider(seeded_fixtures_dir), CalendarProvider)
    assert isinstance(MockPaymentProvider(seeded_fixtures_dir), PaymentProvider)
    assert isinstance(MockSubscriptionProvider(seeded_fixtures_dir), SubscriptionProvider)


def test_email_provider_still_has_no_send_method(seeded_fixtures_dir: Path):
    """The safety guarantee is the absence of the method."""
    assert not hasattr(MockEmailProvider(seeded_fixtures_dir), "send")


# --------------------------------------------------------------------------
# Household validation
# --------------------------------------------------------------------------


def test_unknown_household_raises_clearly(seeded_fixtures_dir: Path):
    provider = MockTransactionProvider(seeded_fixtures_dir)
    with pytest.raises(UnknownHouseholdError, match="hh_other"):
        provider.fetch_since("hh_other", EPOCH)


# --------------------------------------------------------------------------
# Missing fixtures fail cleanly, per file
# --------------------------------------------------------------------------


def test_missing_household_json_fails_cleanly(tmp_path: Path):
    empty_dir = tmp_path / "fixtures"
    empty_dir.mkdir()
    provider = MockTransactionProvider(empty_dir)
    with pytest.raises(FixturesNotFoundError, match="household.json"):
        provider.fetch_since(HOUSEHOLD_ID, EPOCH)


def test_missing_inbox_dir_fails_cleanly(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "household.json").write_text(
        json.dumps({"household_id": HOUSEHOLD_ID, "display_name": "x", "created_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    provider = MockEmailProvider(fixtures_dir)
    with pytest.raises(FixturesNotFoundError, match="inbox"):
        provider.fetch_since(HOUSEHOLD_ID, EPOCH)


def test_missing_transactions_json_fails_cleanly(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "household.json").write_text(
        json.dumps({"household_id": HOUSEHOLD_ID, "display_name": "x", "created_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    provider = MockTransactionProvider(fixtures_dir)
    with pytest.raises(FixturesNotFoundError, match="transactions.json"):
        provider.fetch_since(HOUSEHOLD_ID, EPOCH)


def test_missing_merchant_history_json_fails_cleanly(seeded_fixtures_dir: Path):
    (seeded_fixtures_dir / "merchant_history.json").unlink()
    provider = MockTransactionProvider(seeded_fixtures_dir)
    with pytest.raises(FixturesNotFoundError, match="merchant_history.json"):
        provider.merchant_history(HOUSEHOLD_ID, "FitLife")


def test_missing_calendar_json_fails_cleanly(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "household.json").write_text(
        json.dumps({"household_id": HOUSEHOLD_ID, "display_name": "x", "created_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    provider = MockCalendarProvider(fixtures_dir)
    with pytest.raises(FixturesNotFoundError, match="calendar.json"):
        provider.fetch_between(HOUSEHOLD_ID, EPOCH, EPOCH + timedelta(days=1))


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------


def test_email_fetch_since_reads_the_inbox(seeded_fixtures_dir: Path):
    provider = MockEmailProvider(seeded_fixtures_dir)
    signals = provider.fetch_since(HOUSEHOLD_ID, EPOCH)

    ids = {s.signal_id for s in signals}
    assert ids == {
        "sig_gas_bill",
        "sig_streamly_trial",
        "sig_streamly_receipt",
        "sig_newsletter",
    }
    gas_bill = next(s for s in signals if s.signal_id == "sig_gas_bill")
    assert gas_bill.merchant == "British Gas"
    assert gas_bill.amount == Money(amount_minor=8420, currency="GBP")
    assert gas_bill.household_id == HOUSEHOLD_ID


def test_email_fetch_since_respects_since_and_ordering(seeded_fixtures_dir: Path):
    provider = MockEmailProvider(seeded_fixtures_dir)
    since = datetime(2026, 8, 20, 12, tzinfo=UTC)

    signals = provider.fetch_since(HOUSEHOLD_ID, since)

    assert [s.signal_id for s in signals] == ["sig_streamly_trial", "sig_streamly_receipt"]


def test_email_fetch_since_respects_limit(seeded_fixtures_dir: Path):
    provider = MockEmailProvider(seeded_fixtures_dir)
    signals = provider.fetch_since(HOUSEHOLD_ID, EPOCH, limit=1)
    assert len(signals) == 1
    assert signals[0].signal_id == "sig_newsletter"  # earliest


def test_email_create_draft_never_sends(seeded_fixtures_dir: Path):
    provider = MockEmailProvider(seeded_fixtures_dir)
    draft_id = provider.create_draft(
        HOUSEHOLD_ID, "billing@fitlife.example", "Cancel please", "Cancel my membership."
    )
    assert draft_id.startswith("draft_")
    assert provider.drafts == [
        {
            "draft_id": draft_id,
            "household_id": HOUSEHOLD_ID,
            "to": "billing@fitlife.example",
            "subject": "Cancel please",
            "body": "Cancel my membership.",
            "in_reply_to": None,
        }
    ]


def test_email_get_thread_groups_by_thread_id(seeded_fixtures_dir: Path):
    provider = MockEmailProvider(seeded_fixtures_dir)
    thread = provider.get_thread(HOUSEHOLD_ID, "thread_streamly")
    assert [s.signal_id for s in thread] == ["sig_streamly_trial", "sig_streamly_receipt"]


# --------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------


def test_transactions_fetch_since_reads_transactions_json(seeded_fixtures_dir: Path):
    provider = MockTransactionProvider(seeded_fixtures_dir)
    signals = provider.fetch_since(HOUSEHOLD_ID, EPOCH)

    assert {s.signal_id for s in signals} == {"sig_fitlife_charge", "sig_electricity"}
    fitlife = next(s for s in signals if s.merchant == "FitLife")
    assert fitlife.amount == Money(amount_minor=3800, currency="GBP")


def test_merchant_history_filters_by_merchant_and_recency(seeded_fixtures_dir: Path):
    provider = MockTransactionProvider(seeded_fixtures_dir)

    fitlife_history = provider.merchant_history(HOUSEHOLD_ID, "FitLife", months=12)
    assert len(fitlife_history) == 7
    assert all(s.merchant is None or s.merchant == "FitLife" for s in fitlife_history)

    unknown = provider.merchant_history(HOUSEHOLD_ID, "Nonexistent Merchant")
    assert unknown == []


# --------------------------------------------------------------------------
# Calendar
# --------------------------------------------------------------------------


def test_calendar_fetch_between_reads_calendar_json(seeded_fixtures_dir: Path):
    provider = MockCalendarProvider(seeded_fixtures_dir)
    window_start = datetime(2026, 9, 1, tzinfo=UTC)
    window_end = datetime(2026, 9, 3, tzinfo=UTC)

    signals = provider.fetch_between(HOUSEHOLD_ID, window_start, window_end)
    assert {s.signal_id for s in signals} == {"sig_dentist_appt", "sig_standing_meeting"}


def test_calendar_find_free_slots_avoids_busy_windows(seeded_fixtures_dir: Path):
    provider = MockCalendarProvider(seeded_fixtures_dir)
    window_start = datetime(2026, 9, 2, 9, 0, tzinfo=UTC)
    window_end = datetime(2026, 9, 2, 16, 0, tzinfo=UTC)

    free = provider.find_free_slots(HOUSEHOLD_ID, window_start, window_end, duration_minutes=30)

    # Busy: 09:15-10:00 (dentist) and 14:00-15:00 (sync). Free gaps: 09:00-09:15
    # (too short for 30 min), 10:00-14:00, 15:00-16:00.
    assert (datetime(2026, 9, 2, 10, 0, tzinfo=UTC), datetime(2026, 9, 2, 14, 0, tzinfo=UTC)) in free
    assert (datetime(2026, 9, 2, 15, 0, tzinfo=UTC), datetime(2026, 9, 2, 16, 0, tzinfo=UTC)) in free
    assert all(end - start >= timedelta(minutes=30) for start, end in free)


def test_calendar_create_event_does_not_touch_the_fixture_file(seeded_fixtures_dir: Path):
    provider = MockCalendarProvider(seeded_fixtures_dir)
    before = (seeded_fixtures_dir / "calendar.json").read_text(encoding="utf-8")

    start = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)
    event_id = provider.create_event(HOUSEHOLD_ID, "Confirm dental check-up", start, start + timedelta(minutes=15))

    assert event_id.startswith("evt_")
    assert (seeded_fixtures_dir / "calendar.json").read_text(encoding="utf-8") == before

    # But it is visible to a subsequent read from the same provider instance.
    signals = provider.fetch_between(HOUSEHOLD_ID, start - timedelta(minutes=1), start + timedelta(hours=1))
    assert any(s.signal_id == event_id for s in signals)


# --------------------------------------------------------------------------
# Payments — no fixture file, in-memory ledger
# --------------------------------------------------------------------------


def test_payments_schedule_and_cancel(seeded_fixtures_dir: Path):
    provider = MockPaymentProvider(seeded_fixtures_dir)
    due = datetime(2026, 8, 28, tzinfo=UTC)

    payment_id = provider.schedule_payment(
        HOUSEHOLD_ID, "British Gas", Money(amount_minor=8420, currency="GBP"), due
    )
    assert payment_id in provider.scheduled

    assert provider.cancel_scheduled_payment(HOUSEHOLD_ID, payment_id) is True
    assert payment_id not in provider.scheduled
    assert provider.cancel_scheduled_payment(HOUSEHOLD_ID, payment_id) is False


def test_payments_require_a_known_household(seeded_fixtures_dir: Path):
    provider = MockPaymentProvider(seeded_fixtures_dir)
    with pytest.raises(UnknownHouseholdError):
        provider.schedule_payment(
            "hh_other", "British Gas", Money(amount_minor=100, currency="GBP"), EPOCH
        )


# --------------------------------------------------------------------------
# Subscriptions — no fixture file, in-memory ledger
# --------------------------------------------------------------------------


def test_subscriptions_cancel_and_downgrade(seeded_fixtures_dir: Path):
    provider = MockSubscriptionProvider(seeded_fixtures_dir)

    receipt = provider.cancel(HOUSEHOLD_ID, "FitLife", "No visits in 90 days")
    assert receipt.startswith("rcpt_")
    assert provider.cancelled[0]["merchant"] == "FitLife"

    receipt2 = provider.downgrade(HOUSEHOLD_ID, "Streamly", "Basic")
    assert receipt2.startswith("rcpt_")
    assert provider.downgraded[0]["target_plan"] == "Basic"
