"""`Providers.as_of` — the fixture world's clock, exposed on the bundle.

The bug this exists to fix: Lane A's `signals.py` computes its lookback window
against `datetime.now(UTC)`. Mock fixtures are anchored to a fixed
`DEFAULT_AS_OF` (2026-08-26). Once real time drifts past that date, a wall-clock
lookback finds every fixture signal outside its window — no exception, a quiet
day that is actually a stale one. `as_of` gives Lane A the fixture world's own
notion of "now" to compute the window against instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from quiet_hours_contracts import ProviderMode

from quiet_hours_integrations.base import Providers
from quiet_hours_integrations.mock import build_mock_providers
from quiet_hours_integrations.mock._fixtures import DEFAULT_AS_OF


def test_as_of_defaults_to_none():
    """`None` means "use wall-clock" — the correct default for `LIVE`, which
    relies on leaving this unset, and for any bundle no one has told otherwise."""
    bundle = Providers(
        mode=ProviderMode.LIVE,
        email=object(),
        transactions=object(),
        calendar=object(),
        payments=object(),
        subscriptions=object(),
    )
    assert bundle.as_of is None


def test_as_of_is_keyword_only_and_does_not_disturb_existing_construction_sites():
    """Every existing call constructs `Providers` with keyword arguments already
    (see `mock/__init__.py`), so omitting `as_of` must keep working unchanged."""
    bundle = Providers(
        mode=ProviderMode.MOCK,
        email=object(),
        transactions=object(),
        calendar=object(),
        payments=object(),
        subscriptions=object(),
    )
    assert bundle.as_of is None


def test_build_mock_providers_sets_as_of_to_the_reference_date(seeded_fixtures_dir: Path):
    bundle = build_mock_providers(seeded_fixtures_dir)
    assert bundle.as_of == DEFAULT_AS_OF


def test_build_mock_providers_accepts_a_different_as_of(seeded_fixtures_dir: Path):
    custom = datetime(2027, 1, 1, tzinfo=UTC)
    bundle = build_mock_providers(seeded_fixtures_dir, as_of=custom)
    assert bundle.as_of == custom
