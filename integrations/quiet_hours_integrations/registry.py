"""Provider selection - the single switch between mock and live.

    providers = get_providers(ProviderMode.MOCK)

Keeping the choice in one place is what makes mock mode a switch rather than a
scattering of conditionals through the agent. Lane A never checks the mode.
"""

from __future__ import annotations

from quiet_hours_contracts import ProviderMode

from .base import Providers


def get_providers(mode: ProviderMode | str, *, fixtures_dir: str | None = None) -> Providers:
    """Build the provider bundle for `mode`.

    `MOCK` must work with zero credentials - it is how judges run the project.
    `LIVE` raises a clear error if credentials are missing rather than failing
    obscurely halfway through a run.
    """
    mode = ProviderMode(mode) if isinstance(mode, str) else mode

    if mode is ProviderMode.MOCK:
        raise NotImplementedError(
            "Lane C: wire the mock providers here. Build order step c/mock-providers."
        )

    raise NotImplementedError(
        "Lane C: wire the live providers here. Build order step c/live-providers."
    )
