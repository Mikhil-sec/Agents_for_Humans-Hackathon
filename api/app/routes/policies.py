"""`/api/policies` — the autonomy the user has granted, and how to take it back.

Judges will look for this screen: it is the answer to "what if it learns the wrong
thing?". Revoke is a `DELETE` that sets `revoked_at` rather than deleting the row,
so a revoked rule stays in the audit trail with the actions it once permitted.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..backends import get_backend
from ..config import DEFAULT_PAGE_SIZE
from ..errors import POLICY_NOT_FOUND, ApiProblem
from ..paging import paginate

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("")
def list_policies(
    include_revoked: bool = Query(default=False),
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    policies = get_backend().list_policies(include_revoked=include_revoked)
    return paginate(policies, cursor=cursor, limit=limit)


@router.delete("/{policy_id}")
def revoke_policy(policy_id: str) -> dict[str, Any]:
    """Revoke a learned rule. Idempotent — revoking twice returns the same row,
    because the user pressing the button again means the same thing both times."""
    policy = get_backend().revoke_policy(policy_id)
    if policy is None:
        raise ApiProblem(POLICY_NOT_FOUND, f"no policy {policy_id}", 404)
    return policy.model_dump(mode="json")
