"""AgentCore Runtime entrypoint — the deployed twin of `local_run.py`.

Amazon Bedrock AgentCore Runtime requires `linux/arm64`, port 8080, `POST
/invocations` and `GET /ping`. `BedrockAgentCoreApp` provides all four; the
container contract lives in `agent/Dockerfile`.

Two entry paths, both streaming:

    {"household_id": "hh_demo"}                          a scheduled run
    {"decision_responses": [<DecisionResponse>, ...]}    resume a suspended run

The resume path is why this file exists at all. EventBridge starts a run; the run
proposes an action that spends money; the policy gate interrupts; the process
ends. Days later Lane B's `POST /api/decisions/{id}/respond` invokes this runtime
again, in a different container, and the *same tool call* completes. Everything
that makes that possible was proved by the A1 and A5 spikes — this module is that
mechanic with an HTTP front door on it.

## What is streamed

Progress, never prose. Quiet Hours' web app is a decision inbox, not a chat, so
forwarding the model's token deltas would put text on a surface with nowhere to
render it and no reason to. The envelopes below are what Lane B consumes:

    {"type": "run_started",       "run_id", "household_id", "session_id"}
    {"type": "node_started",      "node"}
    {"type": "node_finished",     "node"}
    {"type": "decision_required", "decision": <DecisionCard>}
    {"type": "run_finished",      "status", "stats", "findings", "brief",
                                  "decisions"}
    {"type": "error",             "error", "message"}

Every payload is plain JSON — contract models dumped with `mode="json"`, never
Strands objects, which are not serialisable and would fail inside the SSE writer
where the traceback is hardest to read.

## Local

    QH_PROVIDER_MODE=mock python -m quiet_hours_agent.main
    curl -XPOST localhost:8080/invocations -H 'Content-Type: application/json' \
      -d '{"household_id":"hh_demo"}'

`bedrock_agentcore` is an optional import. Mock mode, the test suite and `make
agent` must all work without it installed — the package is only needed to *serve*
this module, not to exercise the cycle underneath it, and requiring it would put
an AWS SDK between a judge and `make demo`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from quiet_hours_contracts import (
    DecisionCard,
    DecisionResponse,
    Run,
    RunStats,
    RunStatus,
    RunTrigger,
)

from .graph import GraphRun, RunHarvest, build_graph, harvest
from .memory import build_memory, recall_block
from .resume import build_resume_payload, persist_decisions, run_status_for, was_interrupted
from .sessions import session_id_for
from .store import Store, build_store, new_id, utcnow

logger = logging.getLogger(__name__)

DEFAULT_TASK = "Do this household's admin for today."

RECALL_QUERY = "household preferences about bills, subscriptions and appointments"
"""What to ask long-term memory for at the start of a run. Broad on purpose: the
run has not triaged anything yet, so there is no narrower question to ask."""


class PayloadError(ValueError):
    """The invocation payload could not be understood."""


# --------------------------------------------------------------------------
# Reading the payload
# --------------------------------------------------------------------------


def _responses_from(payload: dict[str, Any]) -> list[DecisionResponse]:
    """Any `DecisionResponse`s in the payload. Empty list means a fresh run.

    Accepts both the singular and plural keys because a graph can suspend on more
    than one decision at once — the specialists run in parallel — and Lane B's
    endpoint answers one card at a time. Both have to work.
    """
    raw = payload.get("decision_responses")
    if raw is None:
        single = payload.get("decision_response")
        raw = [single] if single is not None else []

    if not isinstance(raw, list):
        raise PayloadError("decision_responses must be a list")

    try:
        return [DecisionResponse.model_validate(item) for item in raw]
    except Exception as exc:
        raise PayloadError(f"could not read decision response: {exc}") from exc


def _household_from(payload: dict[str, Any]) -> str:
    household = str(payload.get("household_id") or "").strip()
    if not household:
        raise PayloadError("household_id is required")
    return household


# --------------------------------------------------------------------------
# Translating Strands events into the wire envelopes
# --------------------------------------------------------------------------


def _envelope_for(event: dict[str, Any]) -> dict[str, Any] | None:
    """One Strands graph event as a wire envelope, or None to drop it.

    A whitelist rather than a passthrough. `multiagent_node_stop` carries a
    `NodeResult`, and `multiagent_result` a `GraphResult`; neither survives
    `json.dumps`, and forwarding them would fail inside the SSE writer rather
    than here. The final result is handled by the caller, which has the run
    context needed to turn it into something useful.
    """
    kind = event.get("type")
    if kind == "multiagent_node_start":
        return {"type": "node_started", "node": event.get("node_id")}
    if kind == "multiagent_node_stop":
        return {"type": "node_finished", "node": event.get("node_id")}
    return None


def _stats_for(run: GraphRun, outcome: RunHarvest) -> RunStats:
    """Measured from the gate's recorded verdicts, never written by a model.

    Same rule as the brief's headline numbers: the autonomy rate is the product's
    central claim, so every figure behind it is counted.

    `signals_ingested` is read off `invocation_state`, where the ungoverned
    `load_signals` tool stashes the real `Signal` objects, rather than off
    anything the model said about them.

    A **resumed** run reports zero signals and zero findings, and that is correct
    rather than a gap: a resumed graph replays only the interrupted node, so
    ingest and triage stay completed and do not run again. Counting them a second
    time would inflate exactly the numbers the autonomy chart is built from.
    """
    verdicts = run.policy_hook.verdicts
    proposed = len(verdicts)
    autonomous = sum(1 for _, verdict in verdicts if verdict.allow_silently)
    return RunStats(
        signals_ingested=len(run.invocation_state.get("signals") or []),
        findings_created=len(outcome.findings),
        actions_proposed=proposed,
        actions_autonomous=autonomous,
        decisions_raised=proposed - autonomous,
        policies_applied=sum(1 for _, verdict in verdicts if verdict.policy_id),
    )


# --------------------------------------------------------------------------
# The cycle
# --------------------------------------------------------------------------


async def run_cycle(payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """One scheduled run, or one resume. Yields wire envelopes.

    Kept separate from the `@app.entrypoint` wrapper so the whole cycle is
    testable without `bedrock_agentcore` installed and without an HTTP server.
    """
    mode = os.environ.get("QH_PROVIDER_MODE", "mock")
    store = build_store(mode)
    responses = _responses_from(payload)

    if responses:
        async for event in _resume(payload, responses, store=store, mode=mode):
            yield event
    else:
        async for event in _fresh_run(payload, store=store, mode=mode):
            yield event


async def _fresh_run(
    payload: dict[str, Any], *, store: Store, mode: str
) -> AsyncIterator[dict[str, Any]]:
    household = _household_from(payload)

    # A household with a suspended run is *waiting on a human*. Starting another
    # would pile a second set of cards onto an inbox nobody has answered yet, and
    # spend a second run's worth of Bedrock tokens re-reasoning about the same
    # unresolved day. Report what is already outstanding instead.
    pending = store.list_pending_decisions(household)
    if pending:
        logger.info("household %s already has %d pending decision(s)", household, len(pending))
        for card in pending:
            yield {"type": "decision_required", "decision": card.model_dump(mode="json")}
        yield {
            "type": "run_finished",
            "status": RunStatus.WAITING_ON_USER.value,
            "household_id": household,
            "decisions": [card.decision_id for card in pending],
            "stats": None,
            "findings": [],
            "brief": None,
        }
        return

    run_id = new_id("run")
    session_id = session_id_for(household, run_id)

    memory = build_memory(household, session_id=session_id, mode=mode)
    run = _build(household, store=store, run_id=run_id, session_id=session_id, mode=mode)

    store.save_run(
        Run(
            run_id=run_id,
            household_id=household,
            trigger=RunTrigger.SCHEDULE,
            status=RunStatus.RUNNING,
            session_id=session_id,
            started_at=utcnow(),
        )
    )

    yield {
        "type": "run_started",
        "run_id": run_id,
        "household_id": household,
        "session_id": session_id,
    }

    # Recalled context goes into the *task*, not `invocation_state` — the exact
    # opposite of how `household_id` travels. Identity must reach tools without
    # entering the model's context; memory is worthless unless it does. See the
    # table at the top of `memory.py` for why that is safe.
    task = "\n\n".join(filter(None, [recall_block(memory.recall(RECALL_QUERY)), DEFAULT_TASK]))

    async for event in _drive(
        run, task, store=store, session_id=session_id, trigger=RunTrigger.SCHEDULE
    ):
        yield event


async def _resume(
    payload: dict[str, Any],
    responses: list[DecisionResponse],
    *,
    store: Store,
    mode: str,
) -> AsyncIterator[dict[str, Any]]:
    """Wake a suspended run with the user's answers."""
    pairs: list[tuple[DecisionCard, DecisionResponse]] = []
    for response in responses:
        card = store.get_decision(response.decision_id)
        if card is None:
            raise PayloadError(f"no decision card {response.decision_id}")
        pairs.append((card, response))

    # The card is authoritative for all three. The runtime session id AgentCore
    # puts on the request identifies *this HTTP conversation*; the Strands
    # session id identifies the suspended graph, was written days ago, and is the
    # only one that rehydrates the pending tool call.
    first = pairs[0][0]
    household = first.household_id
    session_id = first.session_id
    run_id = first.run_id

    memory = build_memory(household, session_id=session_id, mode=mode)
    run = _build(household, store=store, run_id=run_id, session_id=session_id, mode=mode)

    yield {
        "type": "run_started",
        "run_id": run_id,
        "household_id": household,
        "session_id": session_id,
        "resumed_from": [card.decision_id for card, _ in pairs],
    }

    async for event in _drive(
        run,
        build_resume_payload(pairs),
        store=store,
        session_id=session_id,
        trigger=RunTrigger.RESUME,
    ):
        yield event

    # Written after the graph has run, so `new_policies` reflects any rule the
    # answer created and the recalled text can explain why the agent will now be
    # quiet about this. Memory is advisory, so a failure here must not fail the
    # run — every method on it already swallows its own exceptions.
    learned = {policy.created_from_decision_id: policy for policy in run.policy_hook.new_policies}
    for card, response in pairs:
        memory.remember_decision(card, response, policy=learned.get(card.decision_id))


def _build(household: str, *, store: Store, run_id: str, session_id: str, mode: str) -> GraphRun:
    """The graph. Must be assembled identically when starting and when resuming —
    the resume rehydrates the first process's state by session id, so a graph
    built differently would not line up with what is on disk."""
    from .sessions import build_session_manager

    session_dir = os.environ.get("QH_SESSION_DIR", ".local/sessions")
    return build_graph(
        household,
        store=store,
        run_id=run_id,
        session_id=session_id,
        session_dir=session_dir,
        session_manager=build_session_manager(session_id, mode=mode, session_dir=session_dir),
        mode=mode,
    )


async def _drive(
    run: GraphRun,
    task: Any,
    *,
    store: Store,
    session_id: str,
    trigger: RunTrigger,
) -> AsyncIterator[dict[str, Any]]:
    """Stream the graph, then persist and report whatever it produced.

    Both the interrupted and the completed case land here, because from this
    module's point of view they differ only in what the final envelope says.
    """
    result: Any = None

    async for event in run.stream(task):
        if event.get("type") == "multiagent_result":
            result = event.get("result")
            continue
        envelope = _envelope_for(event)
        if envelope is not None:
            yield envelope

    if result is None:
        # The stream ended without a result event, which should not happen — but
        # a run whose cards were never written is a run the user cannot answer,
        # so say so loudly rather than reporting a quiet success.
        yield {"type": "error", "error": "no_result", "message": "graph produced no result"}
        return

    interrupted = was_interrupted(result)
    cards = persist_decisions(result, store, session_id=session_id) if interrupted else []
    for card in cards:
        yield {"type": "decision_required", "decision": card.model_dump(mode="json")}

    outcome = harvest(result, run, pending_decision_ids=[card.decision_id for card in cards])
    stats = _stats_for(run, outcome)

    store.save_run(
        Run(
            run_id=run.run_id,
            household_id=run.household_id,
            trigger=trigger,
            status=run_status_for(result),
            session_id=session_id,
            started_at=utcnow(),
            finished_at=None if interrupted else utcnow(),
            stats=stats,
        )
    )

    yield {
        "type": "run_finished",
        "status": run_status_for(result).value,
        "run_id": run.run_id,
        "household_id": run.household_id,
        "stats": stats.model_dump(mode="json"),
        "findings": [finding.model_dump(mode="json") for finding in outcome.findings],
        "brief": outcome.brief.model_dump(mode="json") if outcome.brief else None,
        "decisions": [card.decision_id for card in cards],
    }


# --------------------------------------------------------------------------
# The HTTP surface
# --------------------------------------------------------------------------


def _build_app() -> Any | None:
    """`BedrockAgentCoreApp`, or None when the package is not installed.

    Returning None rather than raising is what keeps `import
    quiet_hours_agent.main` working in mock mode and under pytest. Only `python
    -m quiet_hours_agent.main` actually needs the server.
    """
    try:
        from bedrock_agentcore import BedrockAgentCoreApp
    except ImportError:  # pragma: no cover - depends on the install, not the code
        logger.debug("bedrock-agentcore not installed; serving is unavailable")
        return None
    return BedrockAgentCoreApp()


app = _build_app()


async def invoke(payload: dict[str, Any], context: Any = None) -> AsyncIterator[dict[str, Any]]:
    """The AgentCore entrypoint.

    An async generator, so AgentCore streams it as SSE. Errors are yielded as an
    `error` envelope rather than raised: a raise mid-stream reaches the client as
    a truncated SSE body with no status code, and "the connection ended" is not
    something Lane B's inbox can render.

    `context` carries AgentCore's own request metadata (`session_id`, headers).
    Deliberately unused for routing — see `_resume` for why the card's session id
    is the one that matters.
    """
    try:
        async for event in run_cycle(payload):
            yield event
    except PayloadError as exc:
        logger.warning("bad invocation payload: %s", exc)
        yield {"type": "error", "error": "bad_payload", "message": str(exc)}
    except Exception as exc:  # the boundary; nothing above this catches
        logger.exception("run failed")
        yield {"type": "error", "error": "run_failed", "message": str(exc)}


if app is not None:  # pragma: no cover - registration, exercised by serving
    invoke = app.entrypoint(invoke)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":  # pragma: no cover
    os.environ.setdefault("QH_PROVIDER_MODE", "mock")
    logging.basicConfig(level=logging.INFO)

    if app is None:
        raise SystemExit(
            "bedrock-agentcore is not installed. `pip install bedrock-agentcore`, or use "
            "`python -m quiet_hours_agent.local_run` for the credential-free demo."
        )
    logger.info("quiet hours agent starting at %s", _utc_now_iso())
    app.run(port=int(os.environ.get("PORT", "8080")))
