"""Quiet Hours API.

Backed by one of two stores, chosen with the `QH_BACKEND` environment variable:

    QH_BACKEND=fixtures   static contract-shaped JSON from /fixtures  (default)
    QH_BACKEND=live       DynamoDB, and resumes real Strands sessions

The fixtures backend is what lets Lane B build every screen without the agent
existing, and it is what `make demo` serves to a judge. **It must always work.**

LANE B: see docs/lanes/LANE_B_WEB.md for the full route list.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from quiet_hours_contracts import CONTRACT_VERSION

BACKEND = os.environ.get("QH_BACKEND", "fixtures")

app = FastAPI(
    title="Quiet Hours API",
    version=CONTRACT_VERSION,
    description="The decision inbox for an agent that only interrupts when it must.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("QH_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness plus the contract version.

    The web app compares `contract_version` against its compiled-in constant and
    shows a banner on a major mismatch. Do not remove it - a stale deploy
    rendering wrong data silently is a real risk during a three-week sprint.
    """
    return {"status": "ok", "backend": BACKEND, "contract_version": CONTRACT_VERSION}


# TODO(Lane B): mount routers - see docs/lanes/LANE_B_WEB.md
#
#   GET    /api/decisions?status=pending      Page<DecisionCard>
#   GET    /api/decisions/{id}                DecisionCard
#   POST   /api/decisions/{id}/respond        DecisionResponse -> {run_id, status}
#   GET    /api/runs, /api/runs/{id}
#   GET    /api/runs/{id}/stream              SSE
#   POST   /api/runs                          trigger (the demo button)
#   GET    /api/activity?autonomous=true      Page<ActivityEntry>
#   GET    /api/policies, DELETE /api/policies/{id}
#   GET    /api/brief/latest                  DailyBrief
#
# The interesting one is POST /decisions/{id}/respond: persist the response, then
# hand `interrupt_id` back to the agent to resume the suspended session.
# Treat session_id / interrupt_id / interrupt_name as OPAQUE - echo, never parse.
