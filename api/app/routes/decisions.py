"""`/api/decisions` — the interrupt surface.

`POST /{id}/respond` is the interesting one. It persists the user's answer and
then hands `interrupt_id` back to the agent to resume the suspended Strands
session, which may have been waiting for days.

**`session_id`, `interrupt_id` and `interrupt_name` are opaque.** They belong to
Strands and Lane A. This module echoes them and never parses, validates or
constructs them.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from quiet_hours_contracts import (
    CONTRACT_VERSION,
    DecisionCard,
    DecisionChoice,
    DecisionResponse,
    DecisionStatus,
)

from ..backends import get_backend
from ..config import DEFAULT_PAGE_SIZE
from ..errors import (
    DECISION_NOT_FOUND,
    DECISION_NOT_PENDING,
    INVALID_CHOICE,
    ApiProblem,
)
from ..paging import paginate

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


class RespondResult(BaseModel):
    """What the web app gets back after answering a card.

    Not a contract model: the contract defines the *request* (`DecisionResponse`)
    and the frozen route list defines this response as `{run_id, status}`. The
    extra fields are additive and the web app treats them as optional.
    """

    run_id: str
    status: str = Field(description="RunStatus of the run this answer resumed")
    decision_id: str
    choice: DecisionChoice
    contract_version: str = CONTRACT_VERSION


def _require(decision_id: str) -> DecisionCard:
    card = get_backend().get_decision(decision_id)
    if card is None:
        raise ApiProblem(DECISION_NOT_FOUND, f"no decision {decision_id}", 404)
    return card


@router.get("")
def list_decisions(
    status: str | None = Query(default="pending"),
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Pending cards by default. `status=all` returns every card, for `/activity`."""
    wanted = None if status in (None, "", "all") else status
    if wanted is not None and wanted not in {s.value for s in DecisionStatus}:
        raise ApiProblem(
            INVALID_CHOICE,
            f"unknown status {status!r}; expected one of "
            + ", ".join(sorted(s.value for s in DecisionStatus)),
            400,
        )
    cards = get_backend().list_decisions(status=wanted)
    return paginate(cards, cursor=cursor, limit=limit)


@router.get("/{decision_id}")
def get_decision(decision_id: str) -> dict[str, Any]:
    return _require(decision_id).model_dump(mode="json")


@router.post("/{decision_id}/respond")
def respond(decision_id: str, response: DecisionResponse) -> dict[str, Any]:
    """Answer a card and resume its run.

    Rejects a choice the card did not offer. The options are the agent's, and a
    choice it never proposed has no matching branch on the other side of the
    interrupt — accepting one would strand the run.
    """
    card = _require(decision_id)

    if card.status is not DecisionStatus.PENDING:
        raise ApiProblem(
            DECISION_NOT_PENDING,
            f"decision {decision_id} is {card.status.value}, not pending",
            409,
        )

    offered = {option.choice for option in card.options}
    if response.choice not in offered:
        raise ApiProblem(
            INVALID_CHOICE,
            f"this card does not offer {response.choice.value!r}; it offers "
            + ", ".join(sorted(c.value for c in offered)),
            400,
        )

    if response.decision_id and response.decision_id != decision_id:
        raise ApiProblem(
            INVALID_CHOICE,
            f"body decision_id {response.decision_id!r} does not match the URL",
            400,
        )

    if response.responded_at.tzinfo is None:
        response = response.model_copy(
            update={"responded_at": response.responded_at.replace(tzinfo=UTC)}
        )

    run_id, status = get_backend().respond(card, response)
    return RespondResult(
        run_id=run_id,
        status=status,
        decision_id=decision_id,
        choice=response.choice,
    ).model_dump(mode="json")
