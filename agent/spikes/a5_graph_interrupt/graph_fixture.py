"""The two-node graph both spike processes build, identically.

Both processes must assemble the *same* graph shape with the *same* session id,
because the second process rehydrates the first one's suspended state. Keeping
the construction in one place is the point: a divergence between the two would
look exactly like the mechanic being broken.

The shape is a miniature of the real A5 graph — one silent node, one node whose
tool spends money:

    triage (file_record, SILENT)  ->  negotiator (cancel_subscription, CONFIRM)

Two constraints discovered by reading `strands` 1.53.0, both of which the real
`graph.py` has to honour as well:

1. **`PolicyHook` goes on each node `Agent`, never on the `GraphBuilder`.**
   `BeforeToolCallEvent` is dispatched by the tool executor through the *agent's*
   hook registry (`strands/tools/executors/_executor.py`). A graph-level hook
   provider only ever sees the multi-agent events — `BeforeNodeCallEvent` and
   friends — so a `PolicyHook` registered there would gate nothing at all while
   looking entirely correct.
2. **The `SessionManager` goes on the `GraphBuilder`, never on a node `Agent`.**
   `_validate_node_executor` raises
   `ValueError("Session persistence is not supported for Graph agents yet.")`
   if a node executor carries its own session manager.
"""

from __future__ import annotations

from pathlib import Path

from strands import Agent
from strands.multiagent import GraphBuilder
from strands.session import FileSessionManager

from quiet_hours_agent.hooks import PolicyHook
from quiet_hours_agent.models import ScriptedModel, ScriptedStep
from quiet_hours_agent.store import JsonStore
from quiet_hours_agent.tools import cancel_subscription, file_record

HOUSEHOLD_ID = "hh_spike_a5"
SESSION_ID = "qh-spike-a5"

TRIAGE_SCRIPT = [
    ScriptedStep(
        "file_record",
        {"merchant": "British Gas", "note": "Bill is in line with last month."},
        tool_use_id="tooluse_a5_triage",
    )
]

NEGOTIATOR_SCRIPT = [
    ScriptedStep(
        "cancel_subscription",
        {"merchant": "FitLife", "monthly_amount_minor": 3800, "reason": "Unused for 90 days."},
        tool_use_id="tooluse_a5_negotiator",
    )
]


def build_spike_graph(store: JsonStore, session_dir: Path, *, run_id: str):
    """Assemble the spike graph. Returns `(graph, policy_hook)`.

    One `PolicyHook` instance is shared by both node agents on purpose: it
    accumulates the run's verdicts and any learned policy across the whole graph,
    which is exactly what the real runner needs for the autonomy numbers.
    """
    session_dir.mkdir(parents=True, exist_ok=True)

    hook = PolicyHook(
        HOUSEHOLD_ID,
        store.list_policies(HOUSEHOLD_ID),
        store,
        run_id=run_id,
    )

    triage = Agent(
        name="triage",
        model=ScriptedModel(script=TRIAGE_SCRIPT, final_text="Filed the gas bill."),
        tools=[file_record],
        hooks=[hook],
        system_prompt="You triage a household's admin signals.",
        callback_handler=None,
    )

    negotiator = Agent(
        name="negotiator",
        model=ScriptedModel(script=NEGOTIATOR_SCRIPT, final_text="Cancellation handled."),
        tools=[cancel_subscription],
        hooks=[hook],
        system_prompt="You act on wasteful subscriptions.",
        callback_handler=None,
    )

    builder = GraphBuilder()
    builder.add_node(triage, "triage")
    builder.add_node(negotiator, "negotiator")
    builder.add_edge("triage", "negotiator")
    builder.set_entry_point("triage")
    builder.set_session_manager(
        FileSessionManager(session_id=SESSION_ID, storage_dir=str(session_dir))
    )

    return builder.build(), hook
