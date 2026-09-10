"""The cursor-pagination envelope.

`Page` is a contract model; this is only the cursor arithmetic. The cursor is an
opaque string to the web app — it happens to be an offset, and nothing may rely
on that.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from quiet_hours_contracts import Page

from .config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from .errors import INVALID_REQUEST, ApiProblem


def _offset(cursor: str | None) -> int:
    if cursor in (None, ""):
        return 0
    try:
        value = int(str(cursor))
    except ValueError:
        raise ApiProblem(INVALID_REQUEST, f"malformed cursor {cursor!r}", 400) from None
    if value < 0:
        raise ApiProblem(INVALID_REQUEST, f"malformed cursor {cursor!r}", 400)
    return value


def paginate(
    items: Sequence[BaseModel],
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Slice `items` and wrap them in the contract `Page` envelope."""
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    start = _offset(cursor)
    window = items[start : start + limit]
    end = start + len(window)
    return Page(
        items=[item.model_dump(mode="json") for item in window],
        next_cursor=str(end) if end < len(items) else None,
    ).model_dump(mode="json")
