"""Quiet Hours integrations — the provider bundle, and its mock and live
implementations.

Re-exports the two mock-fixture exceptions so a consumer can name them without
reaching into `mock/`:

    from quiet_hours_integrations import FixturesNotFoundError, UnknownHouseholdError

They live here rather than in `base.py`. `base.py` is the Protocol contract —
implementation-agnostic, satisfied equally by `mock/` and `live/` — and these
two are intrinsically about reading fixture files off disk; a live provider
never raises either. Re-exporting them from `base.py` would have the contract
import from one specific implementation, which is backwards. The package root
takes no position on mock vs. live, so it can aggregate this without that
inversion.
"""

from __future__ import annotations

from .mock._fixtures import FixturesNotFoundError, UnknownHouseholdError

__all__ = ["FixturesNotFoundError", "UnknownHouseholdError"]
