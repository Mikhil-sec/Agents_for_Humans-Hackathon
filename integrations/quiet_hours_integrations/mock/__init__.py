"""Mock providers — read `/fixtures`, work with zero credentials.

`build_mock_providers` is the only thing `registry.py` needs from this package.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from quiet_hours_contracts import ProviderMode

from ..base import Providers
from ._fixtures import DEFAULT_AS_OF, require_fixture_set
from .calendar import MockCalendarProvider
from .email import MockEmailProvider
from .payments import MockPaymentProvider
from .subscriptions import MockSubscriptionProvider
from .transactions import MockTransactionProvider

__all__ = ["build_mock_providers"]


def build_mock_providers(fixtures_dir: Path, as_of: datetime = DEFAULT_AS_OF) -> Providers:
    """Build the mock bundle. Fails immediately, before any provider is handed
    back, if the raw fixture set is not fully present — see
    `_fixtures.require_fixture_set` for why this cannot be left to each
    provider's own lazy read."""
    require_fixture_set(fixtures_dir)
    return Providers(
        mode=ProviderMode.MOCK,
        email=MockEmailProvider(fixtures_dir),
        transactions=MockTransactionProvider(fixtures_dir, as_of=as_of),
        calendar=MockCalendarProvider(fixtures_dir),
        payments=MockPaymentProvider(fixtures_dir),
        subscriptions=MockSubscriptionProvider(fixtures_dir),
    )
