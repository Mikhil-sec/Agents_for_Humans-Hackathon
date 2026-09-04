"""`/api/health` — liveness plus the contract version.

The web app compares `contract_version` against its compiled-in constant and shows
a banner on a major mismatch. **Do not remove it.** A stale deploy rendering wrong
data silently is a real risk on a three-week sprint, and this product's failure
mode is quiet by design — an empty inbox is a *good* day, so it cannot also be how
a broken deploy looks.
"""

from __future__ import annotations

from fastapi import APIRouter
from quiet_hours_contracts import CONTRACT_VERSION

from ..backends import get_backend

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "backend": get_backend().name,
        "contract_version": CONTRACT_VERSION,
    }
