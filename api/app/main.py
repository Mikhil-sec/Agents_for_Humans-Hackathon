"""Quiet Hours API.

Backed by one of two stores, chosen with the `QH_BACKEND` environment variable:

    QH_BACKEND=fixtures   static contract-shaped JSON from /fixtures  (default)
    QH_BACKEND=live       DynamoDB, and resumes real Strands sessions

The fixtures backend is what lets Lane B build every screen without the agent
existing, and it is what `make demo` serves to a judge. **It must always work.**

Routes (frozen alongside the contracts, `docs/lanes/LANE_B_WEB.md`):

    GET    /api/decisions?status=pending        Page<DecisionCard>
    GET    /api/decisions/{id}                  DecisionCard
    POST   /api/decisions/{id}/respond          DecisionResponse -> {run_id, status}
    GET    /api/runs                            Page<Run>
    GET    /api/runs/{id}                       Run
    GET    /api/runs/{id}/stream                SSE - live agent progress
    POST   /api/runs                            trigger a run (the demo button)
    GET    /api/activity?autonomous=true        Page<ActivityEntry>
    GET    /api/policies                        Page<Policy>
    DELETE /api/policies/{id}                   revoke
    GET    /api/brief/latest                    DailyBrief
    GET    /api/health                          { status, contract_version }

Two additive routes beyond that list, both serving existing contract models:
`GET /api/household` (the web app needs `Household.timezone` to render UTC
timestamps in local time) and `GET /api/brief/latest/preview` (the digest email
template as HTML, so it can be reviewed without sending anything).

LANE B: see docs/lanes/LANE_B_WEB.md for the full brief.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from quiet_hours_contracts import CONTRACT_VERSION

from .backends import get_backend
from .config import BACKEND, CORS_ORIGINS
from .errors import install_error_handlers
from .routes import activity, brief, decisions, health, policies, runs

app = FastAPI(
    title="Quiet Hours API",
    version=CONTRACT_VERSION,
    description="The decision inbox for an agent that only interrupts when it must.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Contract-Version"],
)

install_error_handlers(app)


@app.middleware("http")
async def contract_version_header(request: Any, call_next: Any) -> Any:
    """Every response carries the contract version, in the body and in a header.

    The header is what lets the web app notice a stale deploy on a response whose
    body is a bare model rather than a `Page` envelope.
    """
    response = await call_next(request)
    response.headers["X-Contract-Version"] = CONTRACT_VERSION
    return response


app.include_router(health.router)
app.include_router(decisions.router)
app.include_router(runs.router)
app.include_router(activity.router)
app.include_router(policies.router)
app.include_router(brief.router)


@app.get("/api/household", tags=["household"])
def household() -> dict[str, Any]:
    """The household this deployment works for.

    Additive to the frozen route list, returning the frozen `Household` model.
    The web app needs `timezone` to convert UTC timestamps at render time and
    `currency` for empty-state copy; hardcoding either in the web app would be a
    contract violation waiting to happen.
    """
    return get_backend().household().model_dump(mode="json")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": "quiet-hours-api",
        "backend": BACKEND,
        "contract_version": CONTRACT_VERSION,
        "docs": "/docs",
    }
