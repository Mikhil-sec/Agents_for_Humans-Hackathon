"""A1 spike, process 2: a brand-new process resumes the suspended run.

Nothing is inherited from process 1 except the files on disk: the DecisionCard
and the Strands session. The agent is rebuilt from scratch with the same session
id and handed the user's answer.

Usage:  python -m spikes.a1_interrupt.step2_resume [approve|deny]

Asserts:
  1. the rebuilt agent accepts the interruptResponse and runs to completion
  2. on approve, the tool executes *now* — in this process, after the answer
  3. on deny, the tool never executes and the cancellation reason is recorded
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from quiet_hours_contracts import DecisionCard, DecisionChoice, DecisionResponse

from .spike import (
    CARD_FILE,
    build_agent,
    log_side_effect,
    read_ledger,
)

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    if not condition:
        failures.append(label)


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "approve").strip().casefold()
    approving = mode == "approve"

    print(f"\n=== PROCESS 2: resume ({mode}) ===")

    if not CARD_FILE.exists():
        print("  No decision card on disk. Run step1_start.py first.")
        return 1

    card = DecisionCard.model_validate_json(CARD_FILE.read_text(encoding="utf-8"))
    print(f"  loaded card   = {card.decision_id}")
    print(f"  interrupt_id  = {card.interrupt_id}")

    ledger_before = read_ledger()
    executed_before = [line for line in ledger_before if "EXECUTED" in line]
    check(not executed_before, "tool still had not executed at the start of process 2")

    log_side_effect(f"PROCESS 2 start (mode={mode})")

    # This is the exact payload Lane B's POST /decisions/{id}/respond produces.
    response = DecisionResponse(
        decision_id=card.decision_id,
        choice=DecisionChoice.APPROVE if approving else DecisionChoice.DENY,
        note="Approved from the spike harness."
        if approving
        else "Declined from the spike harness.",
        responded_at=datetime.now(UTC),
    )

    resume_payload = [
        {
            "interruptResponse": {
                "interruptId": card.interrupt_id,
                "response": response.model_dump(mode="json"),
            }
        }
    ]
    print(f"  resume payload=\n{json.dumps(resume_payload, indent=2)}")

    # A completely fresh agent — same session id, nothing else carried over.
    agent = build_agent()
    result = agent(resume_payload)

    print(f"\n  stop_reason = {result.stop_reason!r}")
    check(result.stop_reason != "interrupt", "resumed run completed (no longer interrupted)")

    ledger_after = read_ledger()
    executed_after = [line for line in ledger_after if "EXECUTED" in line]

    if approving:
        check(len(executed_after) == 1, "tool executed exactly once, in process 2")
    else:
        check(not executed_after, "tool never executed after a denial")

    resumed_lines = [line for line in ledger_after if "GATE resumed" in line]
    check(len(resumed_lines) == 1, "the hook was re-entered once and received the answer")

    print(f"  final message = {json.dumps(result.message, default=str)}")

    # The cancellation surfaces in the *tool result*, not the final assistant
    # message — `result.message` is only the last assistant turn.
    tool_results = [
        block["toolResult"]
        for message in agent.messages
        for block in message.get("content", [])
        if isinstance(block, dict) and "toolResult" in block
    ]
    check(len(tool_results) == 1, f"exactly one tool result recorded (got {len(tool_results)})")

    if tool_results:
        outcome = tool_results[0]
        print(f"  tool result   = {json.dumps(outcome, default=str)}")
        blob = json.dumps(outcome, default=str).casefold()
        if approving:
            check(outcome.get("status") == "success", "tool result status is 'success'")
            check("cancelled fitlife" in blob, "tool result carries the real cancellation")
        else:
            check(outcome.get("status") == "error", "tool result status is 'error'")
            check("declined" in blob, "the denial reason reached the tool result")

    log_side_effect(f"PROCESS 2 exit (mode={mode})")

    print(f"\n  {len(failures)} failure(s) in process 2")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
