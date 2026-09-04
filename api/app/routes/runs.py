"""`/api/runs` — what the agent did, and a live view of it doing it.

`GET /{id}/stream` is Server-Sent Events. The event payloads are **not** contract
models: `/contracts` describes stored state, and these are transport-only progress
frames that nothing persists. `web/lib/stream.ts` holds the matching type. If the
stream ever needs to carry a stored shape, it sends the contract model whole
(as `run.completed` does) rather than a paraphrase of it.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from quiet_hours_contracts import CONTRACT_VERSION, RunStatus

from ..backends import get_backend
from ..config import DEFAULT_PAGE_SIZE
from ..errors import RUN_NOT_FOUND, ApiProblem
from ..paging import paginate

router = APIRouter(prefix="/api/runs", tags=["runs"])

GRAPH_NODES = [
    ("ingest", "Reading email, transactions and calendar"),
    ("triage", "Sorting what matters from what does not"),
    ("analysis", "Checking bills, renewals and price changes"),
    ("policy", "Applying the rules you have already granted"),
    ("brief", "Writing the daily brief"),
]
"""The `GraphBuilder` pipeline, for the progress stream. Mirrors
`docs/ARCHITECTURE.md`; it is a narration of the run, not a source of truth."""

STEP_SECONDS = 0.6


@router.get("")
def list_runs(cursor: str | None = None, limit: int = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
    return paginate(get_backend().list_runs(), cursor=cursor, limit=limit)


@router.post("")
def trigger_run() -> dict[str, Any]:
    """The demo button. Starts a run and returns it immediately — the client
    follows `/{run_id}/stream` for progress."""
    return get_backend().trigger_run().model_dump(mode="json")


@router.get("/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = get_backend().get_run(run_id)
    if run is None:
        raise ApiProblem(RUN_NOT_FOUND, f"no run {run_id}", 404)
    return run.model_dump(mode="json")


def _frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _events(run_id: str) -> AsyncIterator[str]:
    backend = get_backend()
    run = backend.get_run(run_id)
    if run is None:
        yield _frame("error", {"error": RUN_NOT_FOUND, "message": f"no run {run_id}"})
        return

    total = len(GRAPH_NODES)
    for index, (node, message) in enumerate(GRAPH_NODES, start=1):
        yield _frame(
            "run.progress",
            {
                "run_id": run_id,
                "node": node,
                "message": message,
                "step": index,
                "of": total,
                "contract_version": CONTRACT_VERSION,
            },
        )
        await asyncio.sleep(STEP_SECONDS)

    finished = backend.get_run(run_id) or run
    pending = [
        card.model_dump(mode="json")
        for card in backend.list_decisions(status="pending")
        if card.run_id == run_id
    ]
    yield _frame(
        "run.completed" if finished.status is not RunStatus.WAITING_ON_USER else "run.waiting",
        {
            "run_id": run_id,
            "run": finished.model_dump(mode="json"),
            "pending_decisions": pending,
            "contract_version": CONTRACT_VERSION,
        },
    )


@router.get("/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    """Live progress for one run.

    A missing run is reported as an `error` frame on an open stream rather than a
    404: `EventSource` gives the browser no way to read the body of a failed
    handshake, so a 404 here reaches the web app as an anonymous connection error.
    """
    return StreamingResponse(
        _events(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
