"""Backend selection.

`QH_BACKEND=fixtures` (the default) must work on a clean clone with no
credentials. If `live` is selected and boto3 cannot reach DynamoDB, we fail loudly
at startup rather than silently serving an empty inbox — an empty decision inbox
is a *valid* state in this product, so a silent failure is indistinguishable from
a good day.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import BACKEND
from .base import Backend


@lru_cache(maxsize=1)
def get_backend() -> Backend:
    if BACKEND == "live":
        from .dynamo import DynamoBackend

        return DynamoBackend()
    from .fixtures import FixturesBackend

    return FixturesBackend()


__all__ = ["Backend", "get_backend"]
