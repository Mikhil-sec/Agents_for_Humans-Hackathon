"""`get_providers` — the single switch Lane A depends on.

Building a `MOCK` bundle checks the whole raw fixture set up front and fails
before returning anything if part of it is missing. That is deliberate: Lane
A's `providers.py` only falls back to its in-lane demo signals while
`get_providers(MOCK)` raises. If a bundle came back looking valid and then
failed later on individual reads, Lane A would see an empty day instead of a
missing-fixtures error, which reads as "nothing going on" rather than "not
seeded yet."
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from quiet_hours_contracts import ProviderMode

from quiet_hours_integrations.base import Providers
from quiet_hours_integrations.mock._fixtures import FixturesNotFoundError
from quiet_hours_integrations.registry import get_providers

from .conftest import HOUSEHOLD_ID


def test_get_providers_mock_returns_a_bundle(seeded_fixtures_dir: Path):
    bundle = get_providers(ProviderMode.MOCK, fixtures_dir=str(seeded_fixtures_dir))
    assert isinstance(bundle, Providers)
    assert bundle.mode is ProviderMode.MOCK
    assert bundle.is_live is False


def test_get_providers_accepts_a_mode_string(seeded_fixtures_dir: Path):
    bundle = get_providers("mock", fixtures_dir=str(seeded_fixtures_dir))
    assert bundle.mode is ProviderMode.MOCK


def test_get_providers_mock_reads_the_seeded_fixtures(seeded_fixtures_dir: Path):
    bundle = get_providers(ProviderMode.MOCK, fixtures_dir=str(seeded_fixtures_dir))
    signals = bundle.email.fetch_since(HOUSEHOLD_ID, datetime(2020, 1, 1, tzinfo=UTC))
    assert signals


def test_get_providers_mock_fails_immediately_without_fixtures_on_disk(tmp_path: Path):
    """This is the fallback trigger Lane A's `providers.py` relies on — see the
    module docstring. It must fail at build time, not on first read."""
    with pytest.raises(FixturesNotFoundError):
        get_providers(ProviderMode.MOCK, fixtures_dir=str(tmp_path / "does-not-exist"))


def test_get_providers_mock_fails_immediately_on_a_partially_seeded_directory(
    seeded_fixtures_dir: Path,
):
    """A household.json with no inbox/ must not look like a usable bundle."""
    for name in ("transactions.json", "calendar.json", "merchant_history.json"):
        (seeded_fixtures_dir / name).unlink()

    with pytest.raises(FixturesNotFoundError):
        get_providers(ProviderMode.MOCK, fixtures_dir=str(seeded_fixtures_dir))


def test_get_providers_live_still_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="live providers"):
        get_providers(ProviderMode.LIVE)
