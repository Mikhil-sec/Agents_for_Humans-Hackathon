"""Multi-agent graph: ingest, triage, the specialists, then the digest.

    ingest -> triage -+-> bill_analyst -+
                      +-> negotiator   -+-> brief
                      +-> scheduler    -+
                      +------------------+   (when nothing needs a specialist)

Verified against `strands-agents` 1.53.0 by the A5 spike
(`agent/spikes/a5_graph_interrupt/`), which proves the A1 interrupt mechanic
still works once every agent is inside a `Graph`. Read its README before changing
anything here. Four findings from A5 shape this file:

1. **`PolicyHook` goes on each node `Agent`, never on the `GraphBuilder`.**
   `BeforeToolCallEvent` is dispatched by the tool executor through the *agent's*
   hook registry. A `GraphBuilder.set_hook_providers([...])` provider only ever
   sees multi-agent events (`BeforeNodeCallEvent` and friends), so a `PolicyHook`
   registered there would gate precisely nothing while looking entirely correct.
   This is the single most dangerous mistake available in this file.
2. **The `SessionManager` goes on the `GraphBuilder`, never on a node `Agent`.**
   Strands raises `ValueError("Session persistence is not supported for Graph
   agents yet.")` if a node executor carries its own. The graph's session
   persists each interrupted node's messages and interrupt state for it.
3. **A resumed graph replays only the interrupted node.** Nodes that completed
   before the interrupt stay completed and do not run again — so their silent
   actions are not duplicated, which the spike asserts explicitly.
4. **Fan-in is ANY, not ALL.** A node becomes ready when one incoming edge from
   the just-completed batch is traversable. The specialists all become ready
   together and therefore complete as one batch, so `brief` still fires once,
   after all of them. The `triage -> brief` shortcut exists for the case where no
   specialist is needed at all — without it a quiet day would never get a digest.

`household_id` and `run_id` travel in `invocation_state`, not in the prompt. They
reach tools and hooks without ever entering the model's context: cheaper, and
they cannot be prompt-injected.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from quiet_hours_contracts import (
    DailyBrief,
    Finding,
    FindingKind,
    Money,
    Policy,
    ProposedAction,
)
from strands import Agent
from strands.multiagent import GraphBuilder
from strands.session import FileSessionManager

from .hooks import PolicyHook
from .mock_reasoning import script_for
from .models import build_model
from .prompts import load_prompt
from .schemas import (
    ActionPlan,
    BriefDraft,
    TriageResult,
    action_from_draft,
    finding_from_draft,
)
from .store import Store, new_id, utcnow
from .tools import BILL_TOOLS, INGEST_TOOLS, NEGOTIATION_TOOLS, SCHEDULING_TOOLS

logger = logging.getLogger(__name__)

NODE_INGEST = "ingest"
NODE_TRIAGE = "triage"
NODE_BILL_ANALYST = "bill_analyst"
NODE_NEGOTIATOR = "negotiator"
NODE_SCHEDULER = "scheduler"
NODE_BRIEF = "brief"

SPECIALISTS = (NODE_BILL_ANALYST, NODE_NEGOTIATOR, NODE_SCHEDULER)

MAX_NODE_EXECUTIONS = 12
"""Six nodes plus headroom for a resume pass. Strands warns when a graph has no
limit at all, and an unbounded graph on a metered model is a bill, not a bug."""

ROUTING: dict[str, frozenset[FindingKind]] = {
    NODE_BILL_ANALYST: frozenset(
        {
            FindingKind.BILL_DUE,
            FindingKind.PRICE_INCREASE,
            FindingKind.UNEXPECTED_CHARGE,
            FindingKind.USAGE_ANOMALY,
        }
    ),
    NODE_NEGOTIATOR: frozenset(
        {
            FindingKind.TRIAL_CONVERTING,
            FindingKind.DUPLICATE_SERVICE,
            FindingKind.UNUSED_SUBSCRIPTION,
            FindingKind.RENEWAL_UPCOMING,
        }
    ),
    NODE_SCHEDULER: frozenset(
        {
            FindingKind.APPOINTMENT_NEEDS_REPLY,
            FindingKind.RENEWAL_UPCOMING,
        }
    ),
}
"""Which findings wake which specialist.

`RENEWAL_UPCOMING` intentionally wakes two: a renewal is both something to push
back on and something to put a date against. `NOTHING_TO_DO` wakes none, which is
the common case and the one the product is built around.
"""


# --------------------------------------------------------------------------
# Reading structured output back off the graph
# --------------------------------------------------------------------------


def structured_output_of(state: Any, node_id: str) -> Any | None:
    """The parsed `structured_output` a node returned, or None.

    Defensive at every step: a node may not have run, may have failed, may have
    been interrupted before producing anything, or may have returned prose when
    the model declined to call the structured-output tool. None of those should
    raise inside an edge condition — an exception there fails the whole run.
    """
    node_result = (getattr(state, "results", None) or {}).get(node_id)
    if node_result is None:
        return None

    try:
        agent_results = node_result.get_agent_results()
    except Exception:
        logger.warning("could not read results from node %s", node_id, exc_info=True)
        return None

    for agent_result in agent_results:
        output = getattr(agent_result, "structured_output", None)
        if output is not None:
            return output
    return None


def _triage_findings(state: Any) -> list[Any]:
    result = structured_output_of(state, NODE_TRIAGE)
    return list(getattr(result, "findings", []) or []) if result is not None else []


def _wakes(node_id: str, state: Any) -> bool:
    kinds = ROUTING[node_id]
    return any(finding.kind in kinds for finding in _triage_findings(state))


def _needs_no_specialist(state: Any) -> bool:
    """True when nothing triage found is any specialist's business.

    Also true when triage produced nothing at all — a run that cannot route still
    owes the user a digest saying so, rather than ending silently.
    """
    return not any(_wakes(node_id, state) for node_id in SPECIALISTS)


# --------------------------------------------------------------------------
# Building the graph
# --------------------------------------------------------------------------


@dataclass
class GraphRun:
    """A built graph and the handles the runner needs afterwards."""

    graph: Any
    policy_hook: PolicyHook
    invocation_state: dict[str, Any]
    household_id: str
    run_id: str

    def __call__(self, task: Any) -> Any:
        """Invoke or resume the graph, always with the same invocation state."""
        return self.graph(task, self.invocation_state)


def _model_for(node_id: str, mode: str | None) -> Any:
    """The node's model: Bedrock in live mode, its mock script in mock mode."""
    script = script_for(node_id)
    return build_model(mode, script=script.steps, final_text=script.final_text)


def _specialist(
    node_id: str,
    *,
    tools: list[Any],
    hook: PolicyHook,
    mode: str | None,
) -> Agent:
    """One specialist agent: its own prompt, its own tools, the shared gate.

    Every specialist carries `hook`. A specialist without it is an ungoverned
    path to someone's bank account — see note 1 in the module docstring.
    """
    return Agent(
        name=node_id,
        model=_model_for(node_id, mode),
        tools=tools,
        hooks=[hook],
        system_prompt=load_prompt(node_id),
        structured_output_model=ActionPlan,
        callback_handler=None,
    )


def build_graph(
    household_id: str,
    *,
    store: Store,
    run_id: str,
    session_id: str,
    session_dir: Path | str,
    policies: list[Policy] | None = None,
    mode: str | None = None,
) -> GraphRun:
    """Assemble the run graph.

    Args:
        household_id: Whose admin this run is about. A tenancy boundary — it is
            set here and passed via `invocation_state`, never inferred by a model.
        store: Where findings, actions, decisions and activity are persisted.
        run_id: Identifies this run across every record it produces.
        session_id: The Strands session. Must be identical when resuming.
        session_dir: Where session state is written.
        policies: Learned rules in force. Loaded from the store when omitted.
        mode: `mock` or `live`. Defaults to `QH_PROVIDER_MODE`.
    """
    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    hook = PolicyHook(
        household_id,
        list(policies) if policies is not None else store.list_policies(household_id),
        store,
        run_id=run_id,
    )

    # Ingest and triage hold no governed tools, so they cannot reach the gate.
    # They still get no `hooks=[hook]` by omission rather than by accident: if
    # either is ever given an action tool, it must be added at the same time.
    ingest = Agent(
        name=NODE_INGEST,
        model=_model_for(NODE_INGEST, mode),
        tools=INGEST_TOOLS,
        system_prompt=load_prompt(NODE_INGEST),
        callback_handler=None,
    )

    triage = Agent(
        name=NODE_TRIAGE,
        model=_model_for(NODE_TRIAGE, mode),
        system_prompt=load_prompt(NODE_TRIAGE),
        structured_output_model=TriageResult,
        callback_handler=None,
    )

    bill_analyst = _specialist(NODE_BILL_ANALYST, tools=BILL_TOOLS, hook=hook, mode=mode)
    negotiator = _specialist(NODE_NEGOTIATOR, tools=NEGOTIATION_TOOLS, hook=hook, mode=mode)
    scheduler = _specialist(NODE_SCHEDULER, tools=SCHEDULING_TOOLS, hook=hook, mode=mode)

    brief = Agent(
        name=NODE_BRIEF,
        model=_model_for(NODE_BRIEF, mode),
        system_prompt=load_prompt(NODE_BRIEF),
        structured_output_model=BriefDraft,
        callback_handler=None,
    )

    builder = GraphBuilder()
    builder.add_node(ingest, NODE_INGEST)
    builder.add_node(triage, NODE_TRIAGE)
    builder.add_node(bill_analyst, NODE_BILL_ANALYST)
    builder.add_node(negotiator, NODE_NEGOTIATOR)
    builder.add_node(scheduler, NODE_SCHEDULER)
    builder.add_node(brief, NODE_BRIEF)

    builder.add_edge(NODE_INGEST, NODE_TRIAGE)

    # Only wake a specialist that has something to do. Every model call the graph
    # skips is money saved and one less chance to invent work for the user.
    builder.add_edge(NODE_TRIAGE, NODE_BILL_ANALYST, condition=_bill_route)
    builder.add_edge(NODE_TRIAGE, NODE_NEGOTIATOR, condition=_negotiator_route)
    builder.add_edge(NODE_TRIAGE, NODE_SCHEDULER, condition=_scheduler_route)

    # The quiet day: nothing to route, but the user still gets told so.
    builder.add_edge(NODE_TRIAGE, NODE_BRIEF, condition=_quiet_day_route)

    for node_id in SPECIALISTS:
        builder.add_edge(node_id, NODE_BRIEF)

    builder.set_entry_point(NODE_INGEST)
    builder.set_max_node_executions(MAX_NODE_EXECUTIONS)
    builder.set_session_manager(
        FileSessionManager(session_id=session_id, storage_dir=str(session_dir))
    )

    invocation_state: dict[str, Any] = {
        "household_id": household_id,
        "run_id": run_id,
        "provider_mode": mode,
        "signals": [],
    }

    return GraphRun(
        graph=builder.build(),
        policy_hook=hook,
        invocation_state=invocation_state,
        household_id=household_id,
        run_id=run_id,
    )


# Named rather than lambdas so a failing route is legible in a stack trace and in
# Strands' own edge logging.
def _bill_route(state: Any) -> bool:
    return _wakes(NODE_BILL_ANALYST, state)


def _negotiator_route(state: Any) -> bool:
    return _wakes(NODE_NEGOTIATOR, state)


def _scheduler_route(state: Any) -> bool:
    return _wakes(NODE_SCHEDULER, state)


def _quiet_day_route(state: Any) -> bool:
    return _needs_no_specialist(state)


# --------------------------------------------------------------------------
# Harvesting a finished (or suspended) run
# --------------------------------------------------------------------------


@dataclass
class RunHarvest:
    """The contract objects a graph run produced, ready to persist or render."""

    findings: list[Finding] = field(default_factory=list)
    actions: list[ProposedAction] = field(default_factory=list)
    brief: DailyBrief | None = None


def harvest(
    result: Any,
    run: GraphRun,
    *,
    pending_decision_ids: list[str] | None = None,
    now: datetime | None = None,
) -> RunHarvest:
    """Promote a graph result into contract objects.

    Identity — ids, timestamps, `household_id`, `run_id` — is assigned here, not
    by any model. See `schemas.py` for why that split exists.
    """
    now = now or utcnow()
    # `GraphResult` and `GraphState` both expose `.results`, so the same reader
    # serves both the edge conditions during the run and the harvest after it.
    source = result

    findings = [
        finding_from_draft(
            draft,
            finding_id=new_id("fin"),
            household_id=run.household_id,
            run_id=run.run_id,
            created_at=now,
        )
        for draft in _triage_findings(source)
    ]

    actions: list[ProposedAction] = []
    for node_id in SPECIALISTS:
        plan = structured_output_of(source, node_id)
        for draft in getattr(plan, "actions", []) or []:
            actions.append(
                action_from_draft(
                    draft,
                    action_id=new_id("act"),
                    household_id=run.household_id,
                    run_id=run.run_id,
                    created_at=now,
                )
            )

    return RunHarvest(
        findings=findings,
        actions=actions,
        brief=_brief_from(
            source,
            run,
            pending_decision_ids=pending_decision_ids or [],
            now=now,
        ),
    )


def _brief_from(
    source: Any,
    run: GraphRun,
    *,
    pending_decision_ids: list[str],
    now: datetime,
) -> DailyBrief | None:
    """Assemble the `DailyBrief`, with the numbers measured rather than written.

    `autonomy_rate` and `savings_this_month` come from the policy hook's recorded
    verdicts, never from the model's text. A brief is the one artefact the user
    reads as fact, so every figure in it has to be counted, not estimated.
    """
    draft = structured_output_of(source, NODE_BRIEF)

    verdicts = run.policy_hook.verdicts
    autonomous = sum(1 for _, verdict in verdicts if verdict.allow_silently)
    autonomy_rate = (autonomous / len(verdicts)) if verdicts else 1.0

    saved = sum(
        action.estimated_impact.amount_minor
        for action, verdict in verdicts
        if verdict.allow_silently and action.estimated_impact
    )

    if draft is None:
        # The brief node did not run — normal when the graph is suspended waiting
        # on the user. Still emit a digest so the run has a renderable record.
        headline = (
            f"{len(pending_decision_ids)} decision(s) need you"
            if pending_decision_ids
            else "Nothing needs you today"
        )
        handled: list[str] = []
    else:
        headline = draft.headline
        handled = list(draft.handled_silently)

    return DailyBrief(
        brief_id=new_id("brf"),
        household_id=run.household_id,
        run_id=run.run_id,
        generated_at=now,
        headline=headline[:120],
        handled_silently=handled,
        pending_decision_ids=pending_decision_ids,
        savings_this_month=Money(amount_minor=saved) if saved else None,
        autonomy_rate=autonomy_rate,
    )
