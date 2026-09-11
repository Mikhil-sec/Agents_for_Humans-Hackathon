"""Shared fixture-file builders for the mock provider tests.

`seeded_fixtures_dir` writes a minimal but complete raw fixture set — one of
each of the five files the mock providers read — into a temp directory, using
the shapes documented in `fixtures/README.md`. Individual tests that need to
prove a specific file is missing build their own partial directory instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

HOUSEHOLD_ID = "hh_demo"

HOUSEHOLD = {
    "household_id": HOUSEHOLD_ID,
    "display_name": "The Okonkwo-Bennett household",
    "timezone": "Europe/London",
    "currency": "GBP",
    "digest_hour_local": 8,
    "quiet_hours_local": [22, 7],
    "created_at": "2026-07-20T09:00:00Z",
}

INBOX = [
    {
        "signal_id": "sig_gas_bill",
        "occurred_at": "2026-08-20T07:00:00Z",
        "source": "mock_gmail",
        "subject": "Your British Gas bill is ready",
        "body": "GBP 84.20, due on the 28th.",
        "merchant": "British Gas",
        "amount": {"amount_minor": 8420, "currency": "GBP"},
    },
    {
        "signal_id": "sig_streamly_trial",
        "occurred_at": "2026-08-21T08:00:00Z",
        "source": "mock_gmail",
        "thread_id": "thread_streamly",
        "subject": "Your Streamly free trial ends in 3 days",
        "body": "After 3 days you will be charged GBP 12.99 a month.",
        "merchant": "Streamly",
        "amount": {"amount_minor": 1299, "currency": "GBP"},
    },
    {
        "signal_id": "sig_streamly_receipt",
        "occurred_at": "2026-08-24T08:00:00Z",
        "source": "mock_gmail",
        "thread_id": "thread_streamly",
        "subject": "Re: Your Streamly free trial",
        "body": "Your first payment has been taken.",
        "merchant": "Streamly",
    },
    {
        "signal_id": "sig_newsletter",
        "occurred_at": "2026-08-19T08:00:00Z",
        "source": "mock_gmail",
        "subject": "5 recipes to try this week",
        "body": "Noise the agent should ignore.",
    },
]

TRANSACTIONS = [
    {
        "signal_id": "sig_fitlife_charge",
        "occurred_at": "2026-08-22T09:00:00Z",
        "source": "mock_bank",
        "merchant": "FitLife",
        "amount": {"amount_minor": 3800, "currency": "GBP"},
        "body": "Monthly gym membership.",
    },
    {
        "signal_id": "sig_electricity",
        "occurred_at": "2026-08-23T09:00:00Z",
        "source": "mock_bank",
        "merchant": "Octopus Energy",
        "amount": {"amount_minor": 9400, "currency": "GBP"},
        "body": "Monthly electricity direct debit.",
    },
]

CALENDAR = [
    {
        "signal_id": "sig_dentist_appt",
        "occurred_at": "2026-09-02T09:15:00Z",
        "end_at": "2026-09-02T10:00:00Z",
        "source": "mock_calendar",
        "subject": "Dental check-up — please confirm",
        "body": "Bridge Street Dental asks you to confirm 48h in advance.",
        "merchant": "Bridge Street Dental",
    },
    {
        "signal_id": "sig_standing_meeting",
        "occurred_at": "2026-09-02T14:00:00Z",
        "end_at": "2026-09-02T15:00:00Z",
        "source": "mock_calendar",
        "subject": "Weekly team sync",
    },
]

MERCHANT_HISTORY = {
    "FitLife": [
        {
            "signal_id": f"hist_fitlife_{i}",
            "occurred_at": f"2026-{month:02d}-05T09:00:00Z",
            "amount": {"amount_minor": 3800, "currency": "GBP"},
        }
        for i, month in enumerate(range(1, 8), start=1)
    ],
    "Octopus Energy": [
        {
            "signal_id": "hist_electricity_1",
            "occurred_at": "2026-07-23T09:00:00Z",
            "amount": {"amount_minor": 9200, "currency": "GBP"},
        }
    ],
}


def write_fixtures(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    (base / "household.json").write_text(json.dumps(HOUSEHOLD), encoding="utf-8")

    inbox_dir = base / "inbox"
    inbox_dir.mkdir(exist_ok=True)
    for message in INBOX:
        (inbox_dir / f"{message['signal_id']}.json").write_text(
            json.dumps(message), encoding="utf-8"
        )

    (base / "transactions.json").write_text(json.dumps(TRANSACTIONS), encoding="utf-8")
    (base / "calendar.json").write_text(json.dumps(CALENDAR), encoding="utf-8")
    (base / "merchant_history.json").write_text(json.dumps(MERCHANT_HISTORY), encoding="utf-8")
    return base


@pytest.fixture
def seeded_fixtures_dir(tmp_path: Path) -> Path:
    return write_fixtures(tmp_path / "fixtures")
