"""The two mock-fixture exceptions are importable from the package root.

Mikhil currently catches `FileNotFoundError` structurally because
`FixturesNotFoundError`/`UnknownHouseholdError` live in `mock/_fixtures.py` and
`agent/` codes against `base.py`, not `mock/`. This is what lets him name the
conditions instead — see `quiet_hours_integrations/__init__.py`'s docstring for
why they're re-exported from the package root rather than from `base.py`
(which would have the Protocol contract import from one specific
implementation) or moved into it (which would misrepresent them as part of the
contract every implementation must satisfy, when only `mock/` raises them).
"""

from __future__ import annotations

import ast
import inspect

from quiet_hours_integrations import FixturesNotFoundError, UnknownHouseholdError
from quiet_hours_integrations.mock._fixtures import (
    FixturesNotFoundError as _MockFixturesNotFoundError,
)
from quiet_hours_integrations.mock._fixtures import (
    UnknownHouseholdError as _MockUnknownHouseholdError,
)


def test_reexported_errors_are_the_same_classes_as_mocks():
    assert FixturesNotFoundError is _MockFixturesNotFoundError
    assert UnknownHouseholdError is _MockUnknownHouseholdError


def test_fixtures_not_found_error_is_still_a_file_not_found_error():
    """Existing code catching `FileNotFoundError` structurally must keep working
    even after callers switch to naming `FixturesNotFoundError` directly."""
    assert issubclass(FixturesNotFoundError, FileNotFoundError)


def test_base_does_not_import_the_mock_package():
    """Guards the dependency direction the design choice depends on: the
    contract must not import from one specific implementation. Checked at the
    import-statement level, not by string search — the module docstring
    legitimately mentions `mock/` in prose."""
    from quiet_hours_integrations import base

    tree = ast.parse(inspect.getsource(base))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) if node.module}

    assert not any("mock" in module for module in imported_modules)
