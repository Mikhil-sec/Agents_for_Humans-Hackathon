"""Process 2: answer the decision and resume the *graph*, days later in theory.

Nothing is carried over in memory. This process rebuilds the graph from scratch,
reads the pending card back out of the store, and hands the answer to
`graph(payload)` — the multi-agent equivalent of what A1 proved for a bare agent.

Usage: `python -m spikes.a5_graph_interrupt.step2_resume approve|deny`
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from quiet_hours_contracts import DecisionChoice, DecisionResponse
from strands.multiagent import Status

from quiet_hours_agent.resume import build_resume_payload
from quiet_hours_agent.store import JsonStore

from .graph_fixture import HOUSEHOLD_ID, build_spike_graph

ARTIFACTS = Path(__file__).parent / "artifacts"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    choice = DecisionChoice(sys.argv[1] if len(sys.argv) > 1 else "approve")

    store = JsonStore(ARTIFACTS / "store")
    run_id = (ARTIFACTS / "run_id.txt").read_text(encoding="utf-8").strip()

    pending = store.list_pending_decisions(HOUSEHOLD_ID)
    print(f"  [2] pending decisions found = {len(pending)}")
    if not pending:
        print("  [2] FAIL: process 1 left nothing to answer.")
        return 1

    # A brand new graph object, in a brand new process. It knows nothing except
    # its session id — everything else comes back off disk.
    graph, hook = build_spike_graph(store, ARTIFACTS / "sessions", run_id=run_id)

    pairs = [
        (
            card,
            DecisionResponse(
                decision_id=card.decision_id,
                choice=choice,
                responded_at=datetime.now(UTC),
            ),
        )
        for card in pending
    ]
    payload = build_resume_payload(pairs)
    print(f"  [2] resuming with '{choice.value}' ...")

    result = graph(payload)

    print(f"  [2] graph status      = {result.status}")
    print(f"  [2] completed nodes   = {result.completed_nodes}")

    if result.status is Status.INTERRUPTED:
        print("  [2] FAIL: the graph interrupted again instead of completing.")
        return 1

    # Did the governed tool actually run (or actually not run, if denied)?
    entries = store.list_activity(HOUSEHOLD_ID)
    gated = [entry for entry in entries if not entry.was_autonomous]
    print(f"  [2] activity entries  = {len(entries)} ({len(gated)} gated)")
    for entry in entries:
        state = "ok " if entry.succeeded else "no "
        mark = "auto " if entry.was_autonomous else "asked"
        print(f"        {state} {mark}  {entry.summary}")

    if not gated:
        print("  [2] FAIL: the gated action produced no audit line.")
        return 1

    approved = choice in (DecisionChoice.APPROVE, DecisionChoice.APPROVE_ALWAYS)
    ran = any(entry.succeeded for entry in gated)

    if approved and not ran:
        print("  [2] FAIL: the user approved but the tool never completed.")
        return 1
    if not approved and ran:
        print("  [2] FAIL: the user declined but the tool ran anyway.")
        return 1

    # The node that had already completed in process 1 must not run a second
    # time — a resumed graph replays the interrupted node only.
    silent_entries = [entry for entry in entries if entry.was_autonomous]
    if len(silent_entries) != 1:
        print(
            f"  [2] FAIL: the already-completed node ran {len(silent_entries)} times; "
            "expected exactly 1."
        )
        return 1

    if choice is DecisionChoice.APPROVE_ALWAYS and not hook.new_policies:
        print("  [2] FAIL: approve_always inside a graph learned no policy.")
        return 1

    print(f"  [2] policies learned  = {len(hook.new_policies)}")
    print("  [2] resumed and finished cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
