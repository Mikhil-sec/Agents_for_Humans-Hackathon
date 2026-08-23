"""Process 1: run the graph until a node's tool call interrupts it.

Expected: `triage` completes silently, `negotiator`'s `cancel_subscription` hits
the policy gate, the whole graph comes back `Status.INTERRUPTED`, and the process
exits leaving a resumable session on disk.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from strands.multiagent import Status

from quiet_hours_agent.resume import persist_decisions
from quiet_hours_agent.store import JsonStore, new_id

from .graph_fixture import HOUSEHOLD_ID, SESSION_ID, build_spike_graph

ARTIFACTS = Path(__file__).parent / "artifacts"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    store = JsonStore(ARTIFACTS / "store")
    run_id = new_id("run")
    (ARTIFACTS / "run_id.txt").write_text(run_id, encoding="utf-8")

    graph, hook = build_spike_graph(store, ARTIFACTS / "sessions", run_id=run_id)

    print("  [1] invoking the graph ...")
    result = graph("Do this household's admin for today.")

    print(f"  [1] graph status      = {result.status}")
    print(f"  [1] interrupts        = {len(result.interrupts)}")
    print(f"  [1] completed nodes   = {result.completed_nodes}")
    print(f"  [1] interrupted nodes = {result.interrupted_nodes}")

    if result.status is not Status.INTERRUPTED:
        print("  [1] FAIL: a CONFIRM tool inside a graph node did not interrupt the graph.")
        return 1

    if not result.interrupts:
        print("  [1] FAIL: status was INTERRUPTED but no interrupts reached GraphResult.")
        return 1

    # The node that ran before the interrupt must still have executed and been
    # audited — a graph interrupt must not roll back completed work.
    silent = [entry for entry in store.list_activity(HOUSEHOLD_ID) if entry.was_autonomous]
    print(f"  [1] silent actions already logged = {len(silent)}")
    for entry in silent:
        print(f"        - {entry.summary}")

    cards = persist_decisions(result, store, session_id=SESSION_ID)
    if not cards:
        print("  [1] FAIL: the interrupt carried no usable DecisionCard payload.")
        return 1

    for card in cards:
        print(f"  [1] raised card       = {card.decision_id}")
        print(f"  [1]   headline        = {card.headline}")
        print(f"  [1]   interrupt_id    = {card.interrupt_id}")

    (ARTIFACTS / "cards.json").write_text(
        json.dumps([card.model_dump(mode="json") for card in cards], indent=2),
        encoding="utf-8",
    )

    # Prove the graph's own session actually landed on disk, since the second
    # process has nothing else to rehydrate from.
    session_files = list((ARTIFACTS / "sessions").rglob("*.json"))
    print(f"  [1] session files on disk = {len(session_files)}")
    if not session_files:
        print("  [1] FAIL: no session was persisted; the run is not resumable.")
        return 1

    print(f"  [1] verdicts recorded by the shared hook = {len(hook.verdicts)}")
    print("  [1] exiting with the run suspended.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
