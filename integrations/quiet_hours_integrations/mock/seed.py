"""Generate the seeded four-week household history.

    python -m quiet_hours_integrations.mock.seed --out fixtures/ [--as-of 2026-08-26]

Design docs: `docs/lanes/LANE_C_FIXTURE_DESIGN.md` (the time axis, `merchant_history.json`)
and `docs/lanes/LANE_C_FIXTURE_DESIGN_WEEKS.md` (the nine scenarios, signal ids, the
scenario manifest Mikhil asked for in `docs/status/FOR_YORVAN.md` §4).

Writes the five raw files (`household.json`, `inbox/*.json`, `transactions.json`,
`calendar.json`, `merchant_history.json`) plus `fixtures/scenarios.json`. It does
**not** write the four derived files (`decisions.json`, `activity.json`,
`policies.json`, `runs.json`) — `export_fixtures` does that as stage two, per
Mikhil's decision recorded in `docs/status/FOR_YORVAN.md` §1.

Two invariants that must hold across every re-seed, because Mikhil's A8 re-keying
in `agent/quiet_hours_agent/scenarios.py` depends on them:

* **Every signal id is a fixed string, with no date or counter that shifts when
  the data does.** `sig_fitlife_renewal`, never `sig_fitlife_renewal_20260821`.
  Re-seeding at a different `--as-of` must produce an identical *set* of ids.
* **Every timestamp is `as_of - <fixed offset>`, never a literal date.** Bumping
  `DEFAULT_AS_OF` (or passing a different `--as-of`) shifts every date in the
  world coherently, preserving every relationship inside it — in particular the
  three-day gap between week 4 closing and the as-of date.

Re-seeding twice at the same `--as-of` produces byte-identical files: nothing
here uses wall-clock time, randomness, or dict-ordering luck (`json.dumps` is
called with `sort_keys=True` throughout, belt-and-braces on top of the fact that
construction order is already deterministic).
"""

from __future__ import annotations

import argparse
import calendar as _calendar
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ._fixtures import DEFAULT_AS_OF

HOUSEHOLD_ID = "hh_demo"

# ---------------------------------------------------------------------------
# The calendar — every date below is `as_of` minus a fixed offset, derived from
# two anchors: the three-day gap after week 4 closes, and a plain 7-day-per-week
# spacing between week-Mondays. See the module docstring for why this matters.
# ---------------------------------------------------------------------------

WEEK4_SUNDAY_OFFSET_DAYS = 3
"""The deliberate gap: week 4's pending card has been sitting for a few days."""

WEEK_SPAN_DAYS = 6
"""Monday to Sunday, inclusive."""

_WEEK4_MONDAY_OFFSET_DAYS = WEEK4_SUNDAY_OFFSET_DAYS + WEEK_SPAN_DAYS  # 9

WEEK_MONDAY_OFFSET_DAYS = {
    1: _WEEK4_MONDAY_OFFSET_DAYS + 3 * 7,  # 30
    2: _WEEK4_MONDAY_OFFSET_DAYS + 2 * 7,  # 23
    3: _WEEK4_MONDAY_OFFSET_DAYS + 1 * 7,  # 16
    4: _WEEK4_MONDAY_OFFSET_DAYS,  # 9
}

HOUSEHOLD_CREATED_OFFSET_DAYS = WEEK_MONDAY_OFFSET_DAYS[1] + 7  # 37 — one week of
# onboarding (accounts connect, history imports) before week 1 opens.

FITLIFE_RENEWAL_NOTICE_OFFSET_DAYS = 1
"""The annual renewal notice arrived yesterday."""

FITLIFE_RENEWAL_DAYS_AHEAD = 6
"""Renewal itself is 6 days *after* as-of. Forward, so it is "days ahead", not
an offset subtracted like everything else in this module."""

TRIAL_SIGNUP_OFFSET_DAYS = 13
TRIAL_CONVERTS_DAYS_AHEAD = 2
"""Converts 2 days after as-of, so the reminder can truthfully say "48 hours"."""


def week_monday(as_of: datetime, week: int) -> datetime:
    base = as_of - timedelta(days=WEEK_MONDAY_OFFSET_DAYS[week])
    return base.replace(hour=0, minute=0, second=0, microsecond=0)


def household_created_at(as_of: datetime) -> datetime:
    dt = as_of - timedelta(days=HOUSEHOLD_CREATED_OFFSET_DAYS)
    return dt.replace(hour=9, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Month-anchored series, for merchant_history.json's twelve months of priors.
# ---------------------------------------------------------------------------


def _add_months(dt: datetime, months: int) -> datetime:
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    day = min(dt.day, _calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _most_recent_monthly_on_or_before(as_of: datetime, day: int, hour: int = 9) -> datetime:
    last_day_this_month = _calendar.monthrange(as_of.year, as_of.month)[1]
    candidate = as_of.replace(
        day=min(day, last_day_this_month), hour=hour, minute=0, second=0, microsecond=0
    )
    if candidate.date() > as_of.date():
        candidate = _add_months(candidate, -1)
    return candidate


def monthly_series(as_of: datetime, day: int, months: int) -> list[datetime]:
    """`months` consecutive monthly occurrences of `day`, most recent first,
    ending at the most recent occurrence on or before `as_of`."""
    anchor = _most_recent_monthly_on_or_before(as_of, day)
    return [_add_months(anchor, -i) for i in range(months)]


def camden_series(as_of: datetime) -> list[datetime]:
    """Council tax: ten monthly instalments, April through January — nothing in
    February or March, which is how UK council tax actually works. Scanning
    twelve consecutive months always contains exactly one of each, so this
    always yields exactly ten regardless of `as_of`."""
    anchor = _most_recent_monthly_on_or_before(as_of, 1)
    months = [_add_months(anchor, -i) for i in range(12)]
    return [d for d in months if d.month not in (2, 3)]


def _deterministic_amount(lo: int, hi: int, index: int) -> int:
    """A fixed, non-random spread across `[lo, hi]` — varied-looking without
    depending on an RNG's algorithm being stable across Python versions."""
    span = hi - lo
    return lo + (span * ((index * 37) % 97)) // 97


def volume_series(
    as_of: datetime, count: int, interval_days: int, amount_range: tuple[int, int]
) -> list[tuple[datetime, int]]:
    """`count` occurrences spaced `interval_days` apart, most recent first,
    ending at `as_of`, each with a deterministically varied amount."""
    lo, hi = amount_range
    return [
        (
            (as_of - timedelta(days=i * interval_days)).replace(
                hour=9, minute=0, second=0, microsecond=0
            ),
            _deterministic_amount(lo, hi, i),
        )
        for i in range(count)
    ]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _money(amount_minor: int) -> dict[str, Any]:
    return {"amount_minor": amount_minor, "currency": "GBP"}


# ---------------------------------------------------------------------------
# household.json
# ---------------------------------------------------------------------------


def build_household(as_of: datetime) -> dict[str, Any]:
    return {
        "household_id": HOUSEHOLD_ID,
        "display_name": "The Okonkwo-Bennett household",
        "timezone": "Europe/London",
        "currency": "GBP",
        "digest_hour_local": 8,
        "quiet_hours_local": [22, 7],
        "created_at": _iso(household_created_at(as_of)),
    }


# ---------------------------------------------------------------------------
# merchant_history.json — twelve months of priors, per merchant.
# ---------------------------------------------------------------------------

BRITISH_GAS_VARIATION = [0, -190, 140, -80, 190, -140, 70, -70, 160, -160, 40, -40]
THAMES_WATER_VARIATION = [0, -90, 60, -40, 90, -60, 30, -30, 80, -80, 20, -20]

# (merchant, id_prefix, day_of_month, months, base_amount_minor, variation_cycle)
FLAT_MONTHLY_MERCHANTS: list[tuple[str, str, int, int, int, list[int] | None]] = [
    ("British Gas", "britishgas", 5, 12, 9450, BRITISH_GAS_VARIATION),
    ("Hyperoptic", "hyperoptic", 12, 12, 3200, None),
    ("Vodafone (A)", "vodafone_a", 18, 12, 1800, None),
    ("Vodafone (T)", "vodafone_t", 18, 12, 1800, None),
    ("Little Acorns Nursery", "nursery", 1, 12, 68000, None),
    ("Thames Water", "thameswater", 22, 12, 3430, THAMES_WATER_VARIATION),
    ("Streamly", "streamly", 8, 12, 1299, None),
    ("Dropbox", "dropbox", 14, 12, 999, None),
    ("Google One", "googleone", 26, 12, 799, None),
    ("TV Licence", "tvlicence", 20, 12, 1375, None),
    ("Octopus Energy", "octopus", 15, 12, 9400, None),
    ("FitLife", "fitlife", 3, 17, 3800, None),
]

# (merchant, id_prefix, count_per_year, interval_days, (lo, hi))
VOLUME_MERCHANTS: list[tuple[str, str, int, int, tuple[int, int]]] = [
    ("Sainsbury's", "sainsburys", 26, 14, (1800, 9400)),
    ("Shell", "shell", 10, 36, (4800, 7200)),
    ("TfL", "tfl", 20, 18, (280, 1640)),
    ("Boots", "boots", 15, 24, (650, 3200)),
    ("Pret A Manger", "pret", 40, 9, (320, 780)),
]

AVIVA_LAST_PREMIUM_MINOR = 21400
AVIVA_RENEWAL_QUOTE_MINOR = round(AVIVA_LAST_PREMIUM_MINOR * 1.22)  # 26108


def build_merchant_history(as_of: datetime) -> dict[str, list[dict[str, Any]]]:
    history: dict[str, list[dict[str, Any]]] = {}

    for merchant, prefix, day, months, base, variation in FLAT_MONTHLY_MERCHANTS:
        dates = monthly_series(as_of, day, months)
        history[merchant] = [
            {
                "signal_id": f"hist_{prefix}_{i + 1}",
                "occurred_at": _iso(dt),
                "amount": _money(base + (variation[i % len(variation)] if variation else 0)),
            }
            for i, dt in enumerate(dates)
        ]

    history["Camden Council"] = [
        {
            "signal_id": f"hist_camden_{i + 1}",
            "occurred_at": _iso(dt),
            "amount": _money(16800),
        }
        for i, dt in enumerate(camden_series(as_of))
    ]

    history["Aviva"] = [
        {
            "signal_id": "hist_aviva_1",
            "occurred_at": _iso(as_of - timedelta(days=365, hours=-9)),
            "amount": _money(AVIVA_LAST_PREMIUM_MINOR),
        }
    ]

    for merchant, prefix, count, interval, amount_range in VOLUME_MERCHANTS:
        history[merchant] = [
            {
                "signal_id": f"hist_{prefix}_{i + 1}",
                "occurred_at": _iso(dt),
                "amount": _money(amount),
            }
            for i, (dt, amount) in enumerate(volume_series(as_of, count, interval, amount_range))
        ]

    return history


# ---------------------------------------------------------------------------
# transactions.json — the four-week window.
# ---------------------------------------------------------------------------


def _txn(signal_id: str, occurred: datetime, merchant: str, amount_minor: int) -> dict[str, Any]:
    return {
        "signal_id": signal_id,
        "occurred_at": _iso(occurred),
        "source": "mock_bank",
        "merchant": merchant,
        "amount": _money(amount_minor),
    }


# (merchant, week, weekday_offset, amount_minor, signal_id)
RECURRING_SPINE: list[tuple[str, int, int, int, str]] = [
    ("Camden Council", 1, 0, 16800, "sig_camden_counciltax"),
    ("Vodafone (A)", 1, 3, 1800, "sig_vodafone_line1"),
    ("Hyperoptic", 2, 1, 3200, "sig_hyperoptic_broadband"),
    ("Vodafone (T)", 2, 3, 1800, "sig_vodafone_line2"),
    ("Dropbox", 2, 4, 999, "sig_dropbox_charge"),
    ("Google One", 3, 2, 799, "sig_googleone_charge"),
    ("TV Licence", 3, 5, 1375, "sig_tvlicence_charge"),
    ("Octopus Energy", 4, 1, 9400, "sig_octopus_charge"),
    ("FitLife", 4, 2, 3800, "sig_fitlife_charge"),
]


def build_transactions(as_of: datetime) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for merchant, week, weekday_offset, amount, signal_id in RECURRING_SPINE:
        occurred = week_monday(as_of, week) + timedelta(days=weekday_offset, hours=9)
        records.append(_txn(signal_id, occurred, merchant, amount))

    # The price rise: this charge already reflects the new price. The email
    # (inbox) that announced it deliberately does not state the figure.
    records.append(
        _txn(
            "sig_streamly_charge",
            week_monday(as_of, 2) + timedelta(days=2, hours=9),
            "Streamly",
            1549,
        )
    )

    # The usage spike: three times the routine baseline.
    records.append(
        _txn(
            "sig_thameswater_spike",
            week_monday(as_of, 3) + timedelta(days=4, hours=9),
            "Thames Water",
            10290,
        )
    )

    # The renewed premium, following week 3's quote email.
    records.append(
        _txn(
            "sig_aviva_charge",
            week_monday(as_of, 4) + timedelta(hours=9),
            "Aviva",
            AVIVA_RENEWAL_QUOTE_MINOR,
        )
    )

    # The double charge: same merchant, same amount, same day, twice.
    pret_day = week_monday(as_of, 3) + timedelta(days=1)
    records.append(_txn("sig_pret_double_1", pret_day.replace(hour=8, minute=15), "Pret A Manger", 485))
    records.append(_txn("sig_pret_double_2", pret_day.replace(hour=18, minute=30), "Pret A Manger", 485))

    # Daily noise: enough volume that file/tag/ledger actions grow week over week.
    for merchant, prefix, _count, _interval, amount_range in VOLUME_MERCHANTS:
        per_week = 2 if merchant == "Sainsbury's" else 1
        for week in range(1, 5):
            for k in range(per_week):
                occurred = week_monday(as_of, week) + timedelta(days=2 * k + 1, hours=12 + k)
                amount = _deterministic_amount(*amount_range, index=week * 10 + k)
                records.append(
                    _txn(f"sig_{prefix}_w{week}_{k + 1}", occurred, merchant, amount)
                )

    return records


# ---------------------------------------------------------------------------
# inbox/*.json
# ---------------------------------------------------------------------------


def _email(
    signal_id: str,
    occurred: datetime,
    subject: str,
    body: str,
    *,
    merchant: str | None = None,
    amount_minor: int | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "signal_id": signal_id,
        "occurred_at": _iso(occurred),
        "source": "mock_gmail",
        "subject": subject,
        "body": body,
    }
    if merchant is not None:
        message["merchant"] = merchant
    if amount_minor is not None:
        message["amount"] = _money(amount_minor)
    if thread_id is not None:
        message["thread_id"] = thread_id
    return message


NOISE_EMAILS: list[tuple[str, int, int, str, str]] = [
    # (id_suffix, week, weekday_offset, subject, body)
    ("recipes", 1, 2, "5 recipes to try this week", "Noise the agent should ignore."),
    ("boots_points", 1, 4, "Your Boots Advantage Card points", "You've earned 340 points this month."),
    ("parcel_1", 1, 6, "Your parcel has been dispatched", "Track your delivery, arriving Thursday."),
    ("weekend_sale", 2, 0, "20% off this weekend only", "Shop now before the offer ends."),
    ("tfl_summary", 2, 3, "Your weekly TfL travel summary", "You made 14 journeys this week."),
    ("newsletter_1", 2, 5, "The Saturday read: five stories worth your time", "This week's roundup."),
    ("parcel_2", 3, 1, "Your parcel is out for delivery", "It should arrive by 6pm today."),
    ("gym_promo", 3, 2, "New classes added this month", "Book your spot before they fill up."),
    ("survey", 3, 4, "How did we do? Tell us in 2 minutes", "Your feedback helps us improve."),
    ("recipes_2", 3, 6, "This week's seasonal recipes", "Noise the agent should ignore."),
    ("loyalty", 4, 0, "You're 200 points from your next reward", "Keep shopping to unlock it."),
    ("newsletter_2", 4, 2, "Your monthly roundup", "Here's what happened this month."),
    ("parcel_3", 4, 4, "Your order has shipped", "Estimated arrival in 3-5 working days."),
    ("app_update", 4, 5, "We've updated our app", "New features, same great service."),
]


def build_inbox(as_of: datetime) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    messages.append(
        _email(
            "sig_britishgas_bill",
            week_monday(as_of, 1) + timedelta(days=1, hours=7),
            "Your British Gas bill is ready",
            "Your bill for this month is GBP 94.20. Last month you paid GBP 92.60.",
            merchant="British Gas",
            amount_minor=9420,
        )
    )
    messages.append(
        _email(
            "sig_nursery_invoice",
            week_monday(as_of, 1) + timedelta(days=0, hours=8),
            "Little Acorns Nursery — this month's invoice",
            "This month's fees are GBP 680.00, payable by the 5th.",
            merchant="Little Acorns Nursery",
            amount_minor=68000,
        )
    )
    messages.append(
        _email(
            "sig_dropbox_receipt",
            week_monday(as_of, 1) + timedelta(days=2, hours=9),
            "Your Dropbox receipt",
            "Thanks for being a Dropbox Plus (2TB) member. Your next payment is GBP 9.99.",
            merchant="Dropbox",
            amount_minor=999,
        )
    )
    messages.append(
        _email(
            "sig_googleone_receipt",
            week_monday(as_of, 1) + timedelta(days=2, hours=11),
            "Your Google One receipt",
            "Thanks for your Google One 2TB membership. Your next payment is GBP 7.99.",
            merchant="Google One",
            amount_minor=799,
        )
    )
    messages.append(
        _email(
            "sig_streamly_price_rise",
            week_monday(as_of, 2) + timedelta(days=1, hours=8),
            "We're updating our prices",
            "We're updating our prices to keep bringing you the shows you love. "
            "This will be reflected in your next payment.",
            merchant="Streamly",
        )
    )
    messages.append(
        _email(
            "sig_aviva_quote",
            week_monday(as_of, 3) + timedelta(days=3, hours=9),
            "Your contents insurance renewal quote",
            "Your renewal quote is GBP 261.08, 22% higher than last year's GBP 214.00.",
            merchant="Aviva",
            amount_minor=AVIVA_RENEWAL_QUOTE_MINOR,
        )
    )
    messages.append(
        _email(
            "sig_thetimes_signup",
            as_of - timedelta(days=TRIAL_SIGNUP_OFFSET_DAYS, hours=-10),
            "Welcome to The Times — your free trial has started",
            "Enjoy full digital access. After your trial you'll pay GBP 24.00 a month.",
            merchant="The Times",
            thread_id="thread_thetimes_trial",
        )
    )
    trial_convert_hours = TRIAL_CONVERTS_DAYS_AHEAD * 24
    messages.append(
        _email(
            "sig_thetimes_reminder",
            as_of.replace(hour=8, minute=0, second=0, microsecond=0),
            f"Your free trial ends in {trial_convert_hours} hours",
            "After that you'll be charged GBP 24.00 a month unless you cancel before then.",
            merchant="The Times",
            amount_minor=2400,
            thread_id="thread_thetimes_trial",
        )
    )
    messages.append(
        _email(
            "sig_fitlife_renewal",
            as_of - timedelta(days=FITLIFE_RENEWAL_NOTICE_OFFSET_DAYS, hours=-10),
            "Your FitLife membership renews soon",
            f"Your annual membership renews in {FITLIFE_RENEWAL_DAYS_AHEAD} days "
            "at GBP 456.00 for the year.",
            merchant="FitLife",
            amount_minor=45600,
        )
    )

    for suffix, week, weekday_offset, subject, body in NOISE_EMAILS:
        messages.append(
            _email(
                f"sig_noise_{suffix}",
                week_monday(as_of, week) + timedelta(days=weekday_offset, hours=10),
                subject,
                body,
            )
        )

    return messages


# ---------------------------------------------------------------------------
# calendar.json
# ---------------------------------------------------------------------------


def build_calendar(as_of: datetime) -> list[dict[str, Any]]:
    dentist_start = week_monday(as_of, 1) + timedelta(days=1, hours=9, minutes=15)
    sync_start = week_monday(as_of, 1) + timedelta(days=1, hours=9, minutes=0)
    return [
        {
            "signal_id": "sig_dentist_appt",
            "occurred_at": _iso(dentist_start),
            "end_at": _iso(dentist_start + timedelta(minutes=45)),
            "source": "mock_calendar",
            "subject": "Dental check-up — please confirm",
            "body": "Bridge Street Dental asks you to confirm 48h in advance.",
            "merchant": "Bridge Street Dental",
        },
        {
            "signal_id": "sig_standing_meeting",
            "occurred_at": _iso(sync_start),
            "end_at": _iso(sync_start + timedelta(hours=1)),
            "source": "mock_calendar",
            "subject": "Weekly team sync",
        },
    ]


# ---------------------------------------------------------------------------
# fixtures/scenarios.json — the manifest Mikhil asked for.
# ---------------------------------------------------------------------------


def build_scenarios(as_of: datetime) -> dict[str, Any]:
    return {
        "dentist_clash": {
            "week": 1,
            "finding_kind": "appointment_needs_reply",
            "action_kind": "reschedule_appointment",
            "risk_tier": "confirm",
            "expected_outcome": "approve",
            "signal_ids": ["sig_dentist_appt", "sig_standing_meeting"],
            "note": "The dentist confirmation clashes with the weekly sync.",
        },
        "duplicate_storage_first": {
            "week": 1,
            "finding_kind": "duplicate_service",
            "action_kind": "cancel_subscription",
            "risk_tier": "confirm",
            "expected_outcome": "snooze",
            "signal_ids": ["sig_dropbox_receipt", "sig_googleone_receipt"],
            "note": "First raised in week 1. Snoozed.",
        },
        "duplicate_storage_resurfaces": {
            "week": 2,
            "finding_kind": "duplicate_service",
            "action_kind": "cancel_subscription",
            "risk_tier": "confirm",
            "expected_outcome": "approve",
            "signal_ids": ["sig_dropbox_receipt", "sig_googleone_receipt"],
            "note": "Resurfaces after the week 1 snooze. Approved this time.",
        },
        "streamly_price_rise": {
            "week": 2,
            "finding_kind": "price_increase",
            "action_kind": "downgrade_plan",
            "risk_tier": "confirm",
            "expected_outcome": "deny",
            "signal_ids": ["sig_streamly_price_rise", "sig_streamly_charge"],
            "note": "The email buries the new number; the charge confirms it.",
        },
        "pret_double_charge": {
            "week": 3,
            "finding_kind": "unexpected_charge",
            "action_kind": "dispute_charge",
            "risk_tier": "never_auto",
            "expected_outcome": "approve",
            "signal_ids": ["sig_pret_double_1", "sig_pret_double_2"],
            "note": "NEVER_AUTO. Interrupts even after three policies are already granted.",
        },
        "thameswater_spike": {
            "week": 3,
            "finding_kind": "usage_anomaly",
            "action_kind": "set_reminder",
            "risk_tier": "notify",
            "expected_outcome": "auto",
            "signal_ids": ["sig_thameswater_spike"],
            "note": "SILENT/NOTIFY: executes and appears in the digest, no money moves.",
        },
        "aviva_renewal_quote": {
            "week": 3,
            "finding_kind": "renewal_upcoming",
            "action_kind": "draft_email",
            "risk_tier": "notify",
            "expected_outcome": "auto",
            "signal_ids": ["sig_aviva_quote", "sig_aviva_charge"],
            "note": "22% above last year's premium.",
        },
        "thetimes_trial_converting": {
            "week": 4,
            "finding_kind": "trial_converting",
            "action_kind": "cancel_subscription",
            "risk_tier": "confirm",
            "expected_outcome": "approve",
            "signal_ids": ["sig_thetimes_signup", "sig_thetimes_reminder"],
            "note": "Converts to GBP 24.00/month 48 hours after the reminder.",
        },
        "fitlife_unused": {
            "week": 4,
            "finding_kind": "unused_subscription",
            "action_kind": "cancel_subscription",
            "risk_tier": "confirm",
            "expected_outcome": "pending",
            "signal_ids": ["sig_fitlife_renewal", "sig_fitlife_charge"],
            "note": "The live card. Renewal notice is the trigger; the charge is the evidence.",
        },
    }


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixtures(out: Path, as_of: datetime) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _write_json(out / "household.json", build_household(as_of))
    _write_json(out / "transactions.json", build_transactions(as_of))
    _write_json(out / "calendar.json", build_calendar(as_of))
    _write_json(out / "merchant_history.json", build_merchant_history(as_of))
    _write_json(out / "scenarios.json", build_scenarios(as_of))

    inbox_dir = out / "inbox"
    inbox_dir.mkdir(exist_ok=True)
    for existing in inbox_dir.glob("*.json"):
        existing.unlink()
    for message in build_inbox(as_of):
        _write_json(inbox_dir / f"{message['signal_id']}.json", message)


def _parse_as_of(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quiet-hours-seed")
    parser.add_argument("--out", type=Path, default=Path("fixtures"))
    parser.add_argument(
        "--as-of",
        type=_parse_as_of,
        default=DEFAULT_AS_OF,
        help="Reference date for the whole fixture world. Defaults to DEFAULT_AS_OF.",
    )
    args = parser.parse_args(argv)

    write_fixtures(args.out, args.as_of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
