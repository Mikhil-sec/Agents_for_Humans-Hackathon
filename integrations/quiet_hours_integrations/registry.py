"""Provider selection - the single switch between mock and live.

    providers = get_providers(ProviderMode.MOCK)

Keeping the choice in one place is what makes mock mode a switch rather than a
scattering of conditionals through the agent. Lane A never checks the mode.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from quiet_hours_contracts import ProviderMode

from .base import Providers
from .mock import build_mock_providers
from .mock._fixtures import DEFAULT_AS_OF

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
"""`<repo root>/fixtures` — three parents up from this file (package dir, then
`integrations/`, then the repo root)."""


def get_providers(
    mode: ProviderMode | str,
    *,
    fixtures_dir: str | None = None,
    as_of: datetime = DEFAULT_AS_OF,
) -> Providers:
    """Build the provider bundle for `mode`.

    `MOCK` must work with zero credentials - it is how judges run the project.
    Building the bundle checks that every raw fixture file is present and raises
    `FixturesNotFoundError` (from `mock._fixtures`) immediately if one is
    missing — Lane A's `providers.py` depends on that failure happening at
    build time, not on the first read, so a half-seeded `/fixtures` falls back
    to its in-lane stand-in instead of silently returning an empty day.

    `as_of` is the fixture world's reference "now" (default: `DEFAULT_AS_OF`,
    2026-08-26) — mock providers that reason about recency, e.g.
    `TransactionProvider.merchant_history`'s twelve-month cutoff, anchor to
    this rather than wall-clock time, so a reader gets the same answer today
    as a re-seed would produce a year from now.

    `LIVE` raises a clear error if credentials are missing rather than failing
    obscurely halfway through a run.
    """
    mode = ProviderMode(mode) if isinstance(mode, str) else mode

    if mode is ProviderMode.MOCK:
        resolved_dir = Path(fixtures_dir) if fixtures_dir is not None else DEFAULT_FIXTURES_DIR
        return build_mock_providers(resolved_dir, as_of=as_of)

    raise NotImplementedError(
        "Lane C: wire the live providers here. Build order step c/live-providers."
    )
