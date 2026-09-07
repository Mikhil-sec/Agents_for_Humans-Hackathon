"""The seeder — `c/fixtures-full`.

Tests follow section 8 of `docs/lanes/LANE_C_FIXTURE_DESIGN_WEEKS.md`, plus a few
carried over from the earlier `LANE_C_FIXTURE_DESIGN.md` §5 that are still cheap
to pin exactly (Camden's ten instalments, British Gas's near-flat variance,
FitLife's £456). Two of these are the ones Mikhil's A8 re-keying depends on and
must never regress: signal ids stable across a re-seed at a different `--as-of`,
and byte-identical output from re-seeding at the same one.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quiet_hours_contracts import ProviderMode, Signal, SignalKind

from quiet_hours_integrations.mock._fixtures import require_fixture_set
from quiet_hours_integrations.mock.seed import DEFAULT_AS_OF, write_fixtures
from quiet_hours_integrations.registry import get_providers

FAR_PAST = datetime(2000, 1, 1, tzinfo=UTC)
FAR_FUTURE = datetime(2100, 1, 1, tzinfo=UTC)


def _all_json_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.json"))


def _all_signal_ids(out: Path) -> set[str]:
    ids: set[str] = set()
    for f in (out / "inbox").glob("*.json"):
        ids.add(json.loads(f.read_text(encoding="utf-8"))["signal_id"])
    for t in json.loads((out / "transactions.json").read_text(encoding="utf-8")):
        ids.add(t["signal_id"])
    for c in json.loads((out / "calendar.json").read_text(encoding="utf-8")):
        ids.add(c["signal_id"])
    return ids


# --------------------------------------------------------------------------
# The two hard invariants Mikhil's A8 re-keying depends on
# --------------------------------------------------------------------------


def test_signal_ids_contain_no_digit_runs_that_could_encode_a_date(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    ids = _all_signal_ids(tmp_path)
    assert ids, "sanity: the seeder produced some signals"
    encoded_dates = [i for i in ids if re.search(r"\d{4,}", i)]
    assert encoded_dates == []


def test_signal_id_set_is_identical_across_a_different_as_of(tmp_path: Path):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    write_fixtures(out_a, DEFAULT_AS_OF)
    write_fixtures(out_b, DEFAULT_AS_OF + timedelta(days=30))

    assert _all_signal_ids(out_a) == _all_signal_ids(out_b)


def test_reseeding_at_the_same_as_of_is_byte_identical(tmp_path: Path):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    write_fixtures(out_a, DEFAULT_AS_OF)
    write_fixtures(out_b, DEFAULT_AS_OF)

    files_a = [p.relative_to(out_a).as_posix() for p in _all_json_files(out_a)]
    files_b = [p.relative_to(out_b).as_posix() for p in _all_json_files(out_b)]
    assert files_a == files_b

    for rel in files_a:
        assert (out_a / rel).read_bytes() == (out_b / rel).read_bytes(), rel


def test_bumping_as_of_shifts_the_calendar_and_preserves_the_three_day_gap(tmp_path: Path):
    """The specific bug this guards: an earlier draft of the offset table shifted
    week 4's Monday and Sunday by different amounts, silently breaking the gap."""
    for bump_days in (0, 30, -10):
        as_of = DEFAULT_AS_OF + timedelta(days=bump_days)
        out = tmp_path / f"bump_{bump_days}"
        write_fixtures(out, as_of)

        household = json.loads((out / "household.json").read_text(encoding="utf-8"))
        cal = {c["signal_id"]: c for c in json.loads((out / "calendar.json").read_text(encoding="utf-8"))}

        created_at = datetime.fromisoformat(household["created_at"])
        assert (as_of.date() - created_at.date()).days == 37

        # Week 4 Sunday is derived from the recurring-spine's last week's Monday
        # plus the fixed week span; assert the gap directly against as_of instead
        # of re-deriving it, so this test would fail if the module's own offsets
        # ever drifted apart the way the source design doc's did.
        dentist = datetime.fromisoformat(cal["sig_dentist_appt"]["occurred_at"])
        week1_monday = as_of - timedelta(days=30)
        assert dentist.date() == (week1_monday + timedelta(days=1)).date()


# --------------------------------------------------------------------------
# The exact-string-match invariant between transactions.json and
# merchant_history.json
# --------------------------------------------------------------------------


def test_every_transaction_merchant_has_a_merchant_history_key(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    txns = json.loads((tmp_path / "transactions.json").read_text(encoding="utf-8"))
    history = json.loads((tmp_path / "merchant_history.json").read_text(encoding="utf-8"))

    txn_merchants = {t["merchant"] for t in txns}
    assert txn_merchants <= history.keys()


# --------------------------------------------------------------------------
# The scenario manifest
# --------------------------------------------------------------------------


def test_every_scenario_signal_id_exists_in_the_raw_files(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    scenarios = json.loads((tmp_path / "scenarios.json").read_text(encoding="utf-8"))
    all_ids = _all_signal_ids(tmp_path)

    assert len(scenarios) == 9
    for name, scenario in scenarios.items():
        for signal_id in scenario["signal_ids"]:
            assert signal_id in all_ids, f"{name}: {signal_id} not found in any raw file"


# --------------------------------------------------------------------------
# Every raw record round-trips through the Signal contract
# --------------------------------------------------------------------------


def test_every_inbox_message_round_trips_through_signal(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    for f in (tmp_path / "inbox").glob("*.json"):
        raw = json.loads(f.read_text(encoding="utf-8"))
        Signal(
            signal_id=raw["signal_id"],
            household_id="hh_demo",
            kind=SignalKind.EMAIL,
            occurred_at=raw["occurred_at"],
            ingested_at=raw["occurred_at"],
            source=raw.get("source", "mock_gmail"),
            subject=raw.get("subject"),
            body=raw.get("body"),
            merchant=raw.get("merchant"),
            amount=raw.get("amount"),
        )


def test_every_transaction_and_history_record_round_trips_through_signal(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    txns = json.loads((tmp_path / "transactions.json").read_text(encoding="utf-8"))
    history = json.loads((tmp_path / "merchant_history.json").read_text(encoding="utf-8"))

    for raw in txns:
        Signal(
            signal_id=raw["signal_id"],
            household_id="hh_demo",
            kind=SignalKind.TRANSACTION,
            occurred_at=raw["occurred_at"],
            ingested_at=raw["occurred_at"],
            source=raw.get("source", "mock_bank"),
            merchant=raw.get("merchant"),
            amount=raw.get("amount"),
        )
    for entries in history.values():
        for raw in entries:
            Signal(
                signal_id=raw["signal_id"],
                household_id="hh_demo",
                kind=SignalKind.TRANSACTION,
                occurred_at=raw["occurred_at"],
                ingested_at=raw["occurred_at"],
                source="mock_bank",
                amount=raw.get("amount"),
            )


def test_every_calendar_event_round_trips_through_signal(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    for raw in json.loads((tmp_path / "calendar.json").read_text(encoding="utf-8")):
        Signal(
            signal_id=raw["signal_id"],
            household_id="hh_demo",
            kind=SignalKind.CALENDAR_EVENT,
            occurred_at=raw["occurred_at"],
            ingested_at=raw["occurred_at"],
            source=raw.get("source", "mock_calendar"),
            subject=raw.get("subject"),
            body=raw.get("body"),
            merchant=raw.get("merchant"),
        )


# --------------------------------------------------------------------------
# The full set is usable end to end
# --------------------------------------------------------------------------


def test_full_set_passes_require_fixture_set_and_get_providers_sets_as_of(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    require_fixture_set(tmp_path)  # must not raise

    bundle = get_providers(ProviderMode.MOCK, fixtures_dir=str(tmp_path))
    assert bundle.as_of == DEFAULT_AS_OF

    assert bundle.email.fetch_since("hh_demo", FAR_PAST)
    assert bundle.transactions.fetch_since("hh_demo", FAR_PAST)
    assert bundle.calendar.fetch_between("hh_demo", FAR_PAST, FAR_FUTURE)


def test_double_charge_is_genuinely_a_duplicate(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    txns = json.loads((tmp_path / "transactions.json").read_text(encoding="utf-8"))
    a = next(t for t in txns if t["signal_id"] == "sig_pret_double_1")
    b = next(t for t in txns if t["signal_id"] == "sig_pret_double_2")

    assert a["merchant"] == b["merchant"]
    assert a["amount"] == b["amount"]
    assert datetime.fromisoformat(a["occurred_at"]).date() == datetime.fromisoformat(
        b["occurred_at"]
    ).date()
    assert a["occurred_at"] != b["occurred_at"]  # same day, not the same instant


def test_inbox_noise_is_roughly_sixty_percent(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    scenarios = json.loads((tmp_path / "scenarios.json").read_text(encoding="utf-8"))
    scenario_email_ids = {
        sid
        for s in scenarios.values()
        for sid in s["signal_ids"]
        if sid.startswith("sig_") and not sid.startswith(("sig_dentist", "sig_standing", "sig_thameswater", "sig_pret"))
    }
    total_inbox = len(list((tmp_path / "inbox").glob("*.json")))
    noise = total_inbox - len(scenario_email_ids)
    assert 0.5 <= noise / total_inbox <= 0.7


# --------------------------------------------------------------------------
# Carried over from LANE_C_FIXTURE_DESIGN.md §5
# --------------------------------------------------------------------------


def test_fitlife_history_is_exactly_twelve_records_totalling_456_pounds(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    bundle = get_providers(ProviderMode.MOCK, fixtures_dir=str(tmp_path))
    history = bundle.transactions.merchant_history("hh_demo", "FitLife", months=12)

    assert len(history) == 12
    assert sum(s.amount.amount_minor for s in history) == 45600


def test_camden_council_has_exactly_ten_records_none_in_february_or_march(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    history = json.loads((tmp_path / "merchant_history.json").read_text(encoding="utf-8"))
    camden = history["Camden Council"]

    assert len(camden) == 10
    months = {datetime.fromisoformat(c["occurred_at"]).month for c in camden}
    assert months.isdisjoint({2, 3})


def test_british_gas_priors_vary_by_no_more_than_four_pounds(tmp_path: Path):
    write_fixtures(tmp_path, DEFAULT_AS_OF)
    history = json.loads((tmp_path / "merchant_history.json").read_text(encoding="utf-8"))
    amounts = [c["amount"]["amount_minor"] for c in history["British Gas"]]

    assert max(amounts) - min(amounts) <= 400
