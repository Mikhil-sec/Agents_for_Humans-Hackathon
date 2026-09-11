"""A1 spike, process 1: run until the agent stops to ask, then exit.

Asserts:
  1. the run stops with `stop_reason == "interrupt"`
  2. the tool did NOT execute
  3. the interrupt survives into a contract-shaped DecisionCard
  4. the session on disk records `activated: true` plus the pending tool call

Then the process exits. Nothing is held in memory. Run `step2_resume.py` next.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from quiet_hours_contracts import (
    DecisionCard,
    DecisionChoice,
    DecisionOption,
    DecisionStatus,
    Evidence,
    Money,
)

from .spike import (
    ACTION_ID,
    ARTIFACTS,
    CARD_FILE,
    HOUSEHOLD_ID,
    INTERRUPT_NAME,
    LEDGER,
    MERCHANT,
    MONTHLY_MINOR,
    RUN_ID,
    SESSION_DIR,
    SESSION_ID,
    build_agent,
    log_side_effect,
    read_ledger,
)

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    if not condition:
        failures.append(label)


def find_session_agent_file() -> dict | None:
    """Locate the persisted agent record so we can inspect the interrupt state."""
    for path in SESSION_DIR.rglob("agent.json"):
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def main() -> int:
    print("\n=== PROCESS 1: start the run ===")

    # Clean slate so the assertions mean something.
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    LEDGER.unlink(missing_ok=True)
    CARD_FILE.unlink(missing_ok=True)

    agent = build_agent()
    log_side_effect("PROCESS 1 start")

    result = agent("Cancel the FitLife subscription.")

    print(f"\n  stop_reason = {result.stop_reason!r}")
    check(result.stop_reason == "interrupt", "run stopped with stop_reason == 'interrupt'")
    check(
        len(result.interrupts) == 1, f"exactly one interrupt raised (got {len(result.interrupts)})"
    )

    if not result.interrupts:
        print("\n  No interrupt to persist — aborting.")
        return 1

    interrupt = result.interrupts[0]
    print(f"  interrupt.id    = {interrupt.id}")
    print(f"  interrupt.name  = {interrupt.name}")
    print(f"  interrupt.reason= {json.dumps(interrupt.reason, indent=2, default=str)}")

    check(interrupt.name == INTERRUPT_NAME, f"interrupt name is {INTERRUPT_NAME!r}")
    check(isinstance(interrupt.reason, dict), "interrupt.reason round-tripped as a dict")

    # 2. The tool must NOT have run.
    executed = [line for line in read_ledger() if "EXECUTED" in line]
    check(not executed, "tool did NOT execute before approval")

    # 3. The interrupt fits the frozen DecisionCard contract.
    reason = interrupt.reason if isinstance(interrupt.reason, dict) else {}
    card = DecisionCard(
        decision_id=f"dec_{RUN_ID}",
        household_id=HOUSEHOLD_ID,
        run_id=RUN_ID,
        action_id=ACTION_ID,
        session_id=SESSION_ID,
        interrupt_id=interrupt.id,
        interrupt_name=interrupt.name,
        headline=reason.get("headline", f"Cancel {MERCHANT}?"),
        body=reason.get("body", ""),
        why_asking=reason.get("why_asking", ""),
        options=[
            DecisionOption(choice=DecisionChoice.APPROVE, label="Cancel it", is_default=True),
            DecisionOption(
                choice=DecisionChoice.APPROVE_ALWAYS,
                label="Always cancel these",
                creates_policy_preview=f"Always cancel {MERCHANT} subscriptions",
            ),
            DecisionOption(choice=DecisionChoice.DENY, label="Keep it"),
        ],
        amount=Money(amount_minor=MONTHLY_MINOR, currency="GBP"),
        estimated_impact=Money(amount_minor=MONTHLY_MINOR * 12, currency="GBP"),
        evidence=[
            Evidence(
                signal_id="sig_a1_spike",
                excerpt=f"{MERCHANT} renews next week at {MONTHLY_MINOR} minor units.",
            )
        ],
        status=DecisionStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    CARD_FILE.write_text(card.model_dump_json(indent=2), encoding="utf-8")
    check(CARD_FILE.exists(), "DecisionCard validated against the frozen contract and persisted")

    # 4. The session on disk carries the suspended state.
    session_agent = find_session_agent_file()
    check(session_agent is not None, "session agent record written to disk")

    if session_agent is not None:
        interrupt_state = session_agent.get("_internal_state", {}).get("interrupt_state", {})
        check(
            interrupt_state.get("activated") is True, "persisted interrupt_state.activated is True"
        )
        check(
            interrupt.id in interrupt_state.get("interrupts", {}),
            "persisted interrupt_state contains this interrupt id",
        )
        check(
            _pending_tool_use_is_persisted(interrupt_state),
            "persisted state carries the pending tool_use message",
        )

    log_side_effect("PROCESS 1 exit (suspended at interrupt)")

    print(f"\n  {len(failures)} failure(s) in process 1")
    return 1 if failures else 0


def _pending_tool_use_is_persisted(interrupt_state: dict) -> bool:
    """Is the half-finished tool call on disk, under whichever key this SDK uses?

    **This is the assertion that matters most in the whole spike.** The interrupt
    id surviving proves the run knows it was asked something; this proves the run
    knows *what it was about to do*. Without it the resumed process would come
    back with an answer and nothing to apply it to.

    Strands moved it between minor versions and both shapes are accepted here,
    because the guarantee we depend on is the same in both and pinning the guard
    to one spelling turns an SDK rename into a red build that says nothing:

    * **<= 1.54** — `interrupt_state["context"]["tool_use_message"]`
    * **>= 1.55** — `interrupt_state["pending_tool_execution"]["assistant_message"]`,
      with `completed_tool_results` beside it

    Verified against 1.53.0 and 1.55.1 on 2026-09-11. The *behaviour* is checked
    for real by `step2_resume`, which resumes in a second process and proves the
    tool ran exactly once and only after the answer — so if a future version
    renames this again, that test still holds the line and this one only needs a
    third spelling.
    """
    context = interrupt_state.get("context") or {}
    if "tool_use_message" in context:
        return True

    pending = interrupt_state.get("pending_tool_execution") or {}
    message = pending.get("assistant_message") or {}
    return any("toolUse" in block for block in message.get("content", []))


if __name__ == "__main__":
    sys.exit(main())
