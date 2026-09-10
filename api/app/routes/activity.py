"""`/api/activity` — the audit trail.

Every action the agent took, autonomous or not. This is the screen that makes the
product trustworthy, so the rule is simple: nothing the agent did is missing from
here, and every row carries the rationale that produced it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..backends import get_backend
from ..config import DEFAULT_PAGE_SIZE
from ..paging import paginate

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
def list_activity(
    autonomous: bool | None = Query(default=None),
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Newest first. Omit `autonomous` for everything, which is the default view —
    the split between "handled silently" and "you decided" is a filter on one
    trail, never two separate lists."""
    entries = get_backend().list_activity(autonomous=autonomous)
    return paginate(entries, cursor=cursor, limit=limit)
