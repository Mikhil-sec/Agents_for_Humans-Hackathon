"""Test fixtures.

Every test runs against the real `/fixtures` files, not a hand-written copy of
them. That is deliberate: the thing most likely to break Lane B is Lane C or Lane
A regenerating `/fixtures` into a shape the API cannot serve, and a test suite
with its own private fixtures would pass happily through exactly that failure.

`get_backend()` is `lru_cache`d, so each test clears it and gets a clean
in-memory copy — otherwise answering a card in one test would resolve it for
every test that followed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backends import get_backend
from app.main import app


@pytest.fixture(autouse=True)
def fresh_backend():
    get_backend.cache_clear()
    yield
    get_backend.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def pending_card(client: TestClient) -> dict:
    """The first pending card in `/fixtures`.

    If this ever comes back empty the demo has no inbox, which is a failure worth
    a loud test rather than a skip.
    """
    page = client.get("/api/decisions?status=pending").json()
    assert page["items"], "no pending decision in /fixtures - run `make fixtures`"
    return page["items"][0]
