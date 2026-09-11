"""Lane A's single point of contact with Lane C's provider bundle.

`integrations.base` defines the `Providers` Protocols and is explicitly "a
contract with Lane A". Those interfaces are real and stable; only the
*implementations* behind `get_providers()` are outstanding, and as of 2026-08-24
it still raises `NotImplementedError` for both modes.

So this module codes against the contract and tolerates the absence of the
implementation, which is what lets A4 be finished on Lane A's side rather than
waiting:

    live  ->  providers required. A missing implementation raises.
    mock  ->  providers if available, otherwise Lane A's own stand-in.

**The asymmetry is the safety rule, and it is the same one `signals.py` already
had.** A live run that quietly fell back to demo data would produce real decision
cards about merchants the household has never heard of, and might act on them.
A mock run that falls back is just the demo, working, which is a hard requirement
in the root `AGENTS.md`.

Everything is cached per mode: `get_providers()` may open credentialed clients,
and the graph's specialists run in parallel and would otherwise each build their
own bundle.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, Any] = {}
_warned: set[str] = set()


class ProvidersUnavailable(RuntimeError):
    """Lane C's providers were required and could not be built."""


def resolve_mode(mode: str | None = None) -> str:
    return (mode or os.environ.get("QH_PROVIDER_MODE") or "mock").strip().casefold()


def get_providers(mode: str | None = None) -> Any | None:
    """Lane C's bundle, or None when mock mode has to manage without it.

    Returns:
        A `Providers` instance, or None in mock mode when Lane C's
        implementation is not there yet.

    Raises:
        ProvidersUnavailable: in live mode, when it is not there. Never falls
            back — see the module docstring.
    """
    resolved = resolve_mode(mode)

    with _lock:
        if resolved in _cache:
            return _cache[resolved]

        bundle = _build(resolved)
        _cache[resolved] = bundle
        return bundle


def _build(mode: str) -> Any | None:
    try:
        from quiet_hours_contracts import ProviderMode
        from quiet_hours_integrations.registry import get_providers as lane_c_providers
    except ImportError as exc:
        if mode == "live":
            raise ProvidersUnavailable(f"cannot import Lane C's integrations: {exc}") from exc
        _warn_once(mode, f"integrations package not importable ({exc})")
        return None

    try:
        bundle = lane_c_providers(ProviderMode.LIVE if mode == "live" else ProviderMode.MOCK)
    except (NotImplementedError, FileNotFoundError) as exc:
        # The only two conditions the fallback exists for, and both mean the same
        # thing: **Lane C's data or code is not there yet.**
        #
        # `NotImplementedError` — the provider bundle has not been written
        #     (`registry.py` still raises this for `LIVE`).
        # `FileNotFoundError` — the bundle exists but the raw fixture set does
        #     not. Lane C's `require_fixture_set()` checks all five files
        #     eagerly, at build time, and raises `FixturesNotFoundError`, which
        #     subclasses `FileNotFoundError`. Caught structurally rather than by
        #     name because the class lives in `mock._fixtures`, a private module
        #     — Lane A codes against `base.py` and does not reach past it.
        #
        # Anything else is a defect in a bundle that *does* exist: a malformed
        # `household.json`, a pydantic validation failure, a bad date. Those now
        # propagate in **both** modes rather than quietly downgrading mock mode
        # to the stand-in, which would hide the breakage behind a demo that still
        # runs but is worse. That is consistent with root rule 3: a clean clone
        # ships committed, valid fixtures, so this can only fire on a genuine bug,
        # and a bug should fail in CI rather than degrade on a judge's machine.
        if mode == "live":
            raise ProvidersUnavailable(f"Lane C's live providers are unavailable: {exc}") from exc
        _warn_once(mode, f"Lane C's mock providers are unavailable ({exc})")
        return None

    logger.info("using Lane C's %s providers", mode)
    return bundle


def _warn_once(mode: str, reason: str) -> None:
    """One line per process, not one per tool call.

    Six specialists times eleven tools times four weeks of replay is a lot of
    identical warnings, and a log that repeats itself is a log nobody reads.
    """
    if mode in _warned:
        return
    _warned.add(mode)
    logger.warning("%s — falling back to Lane A's in-lane stand-in", reason)


def reset_cache() -> None:
    """Forget the cached bundle. For tests, and for the replay, which switches
    modes within one process."""
    with _lock:
        _cache.clear()
        _warned.clear()
