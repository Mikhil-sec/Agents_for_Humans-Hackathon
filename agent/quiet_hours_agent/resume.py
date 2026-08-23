"""Suspending and resuming a run around a user decision.

The runner-side half of the interrupt mechanic. The hook (`hooks.py`) raises the
interrupt; this module turns what comes back into persisted `DecisionCard`s, and
later turns the user's `DecisionResponse` into the payload that wakes the run up.

Proven end to end across a real process boundary by the A1 spike
(`agent/spikes/a1_interrupt/`). The payload shape below is what Lane B's
`POST /api/decisions/{id}/respond` ultimately feeds back in.
"""

from __future__ import annotations

import logging
from typing import Any

from quiet_hours_contracts import DecisionCard, DecisionResponse, RunStatus

from .hooks import card_from_interrupt
from .store import Store

logger = logging.getLogger(__name__)

INTERRUPT_STOP_REASON = "interrupt"

INTERRUPTED_STATUS = "interrupted"
"""`Status.INTERRUPTED.value`, compared as a plain string so this module stays
usable whether it is handed an `AgentResult` or a `GraphResult`."""


class ResumeError(RuntimeError):
    """The resume payload could not be built or would strand the run."""


def was_interrupted(result: Any) -> bool:
    """Whether this run stopped to ask the user something.

    Two shapes, because A5 put the agents inside a graph and both still occur:

    * a bare `AgentResult` reports `stop_reason == "interrupt"`;
    * a `GraphResult` has no `stop_reason` at all and reports
      `status == Status.INTERRUPTED` instead.

    Checking only the first silently returned False for every suspended graph —
    the run would look complete, its decision cards would never be written, and
    the session would sit on disk with nothing pointing at it.
    """
    if getattr(result, "stop_reason", None) == INTERRUPT_STOP_REASON:
        return True

    status = getattr(result, "status", None)
    return getattr(status, "value", status) == INTERRUPTED_STATUS


def persist_decisions(result: Any, store: Store, *, session_id: str) -> list[DecisionCard]:
    """Turn the interrupts on an `AgentResult` into saved decision cards.

    Runs immediately after the agent returns. Per A1, `interrupt()` hands control
    back cleanly rather than killing the process, so this is a reliable place to
    persist — and the only place that knows the authoritative `interrupt_id`.
    """
    cards: list[DecisionCard] = []
    for interrupt in getattr(result, "interrupts", []) or []:
        card = card_from_interrupt(interrupt, session_id=session_id)
        if card is None:
            continue
        store.save_decision(card)
        cards.append(card)
        logger.info("raised decision %s (%s)", card.decision_id, card.headline)
    return cards


def interrupt_response_block(interrupt_id: str, response: DecisionResponse) -> dict[str, Any]:
    """One `interruptResponse` content block.

    Guards the two failure modes A1 turned up, both of which strand a run
    silently rather than erroring at the time:

    * a null response never resolves an interrupt — Strands only treats one as
      answered when `Interrupt.response is not None`, so the run would stay
      suspended forever and the card would sit pending with no way back;
    * a mismatched id raises `KeyError: no interrupt found` inside the agent.
    """
    if not interrupt_id:
        raise ResumeError("interrupt_id is required to resume a run")
    if response is None:  # type: ignore[comparison-overlap]
        raise ResumeError("response must not be null — a null answer suspends the run forever")

    return {
        "interruptResponse": {
            "interruptId": interrupt_id,
            "response": response.model_dump(mode="json"),
        }
    }


def build_resume_payload(
    pairs: list[tuple[DecisionCard, DecisionResponse]],
) -> list[dict[str, Any]]:
    """The full resume payload: always a **list**, even for a single decision.

    Strands raises `TypeError` if a run in an interrupt state is resumed with
    anything that is not a list of `interruptResponse` blocks.
    """
    if not pairs:
        raise ResumeError("nothing to resume with")

    return [
        interrupt_response_block(card.interrupt_id, response)
        for card, response in pairs
        if _matches(card, response)
    ]


def _matches(card: DecisionCard, response: DecisionResponse) -> bool:
    if card.decision_id != response.decision_id:
        raise ResumeError(
            f"response for {response.decision_id} does not match card {card.decision_id}"
        )
    return True


def resume_agent(agent: Any, pairs: list[tuple[DecisionCard, DecisionResponse]]) -> Any:
    """Resume a suspended agent with one or more answers.

    The agent must be built with the same `session_id` as the run that was
    suspended. It does not need to be the same process — that is the whole point.
    """
    payload = build_resume_payload(pairs)
    logger.info("resuming %d decision(s)", len(payload))
    return agent(payload)


def run_status_for(result: Any) -> RunStatus:
    """Map an `AgentResult` onto the run lifecycle Lane B renders."""
    return RunStatus.WAITING_ON_USER if was_interrupted(result) else RunStatus.COMPLETED
