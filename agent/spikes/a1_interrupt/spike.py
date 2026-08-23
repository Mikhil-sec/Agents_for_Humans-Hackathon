"""A1 interrupt spike — shared pieces for both processes.

Everything both the "start" process and the "resume" process need: the one
governed tool, the approval hook, and the agent factory. Both processes build
the agent the *same* way — that is the point. Resume is not a special code path,
it is the same agent pointed at the same session id.

Deliberately minimal, per the A1 brief: no graph, no policy engine, no real
model. One hard-coded tool, one hook, one question.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from strands import Agent, tool
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from strands.session import FileSessionManager

from .scripted_model import ScriptedModel

# -- Fixed identifiers -----------------------------------------------------

INTERRUPT_NAME = "qh-approval"
"""Must match `quiet_hours_agent.hooks.INTERRUPT_NAME`."""

SESSION_ID = "a1-spike-session"
HOUSEHOLD_ID = "hh_spike"
RUN_ID = "run_a1_spike"
ACTION_ID = "act_a1_spike"

TOOL_USE_ID = "tooluse_a1_spike_0001"
"""Hard-coded so the spike is reproducible. Real Bedrock generates these, but
they are persisted in the session, so the interrupt id stays stable either way —
see `BeforeToolCallEvent._interrupt_id`."""

MERCHANT = "FitLife"
MONTHLY_MINOR = 3800

ARTIFACTS = Path(__file__).parent / "artifacts"
SESSION_DIR = ARTIFACTS / "sessions"
LEDGER = ARTIFACTS / "side_effects.log"
CARD_FILE = ARTIFACTS / "decision_card.json"

APPROVING_CHOICES = {"approve", "approve_always", "edit"}
"""Everything else — including anything unrecognised — means no. Fail closed."""


def now() -> str:
    return datetime.now(UTC).isoformat()


def log_side_effect(text: str) -> None:
    """Append to the ledger that proves *when* the tool really ran.

    This is the spike's actual evidence. If the cancellation line appears in
    process 1 the mechanic is broken — the point is that it must not exist until
    the user has answered, in process 2.
    """
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(f"{now()} | {text}\n")


def read_ledger() -> list[str]:
    if not LEDGER.exists():
        return []
    return [line for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]


# -- The one governed tool -------------------------------------------------


@tool
def cancel_subscription(merchant: str, monthly_amount_minor: int) -> str:
    """Cancel a recurring subscription.

    Args:
        merchant: The service to cancel.
        monthly_amount_minor: Current monthly charge in minor units.
    """
    log_side_effect(
        f"EXECUTED cancel_subscription merchant={merchant} minor={monthly_amount_minor}"
    )
    return f"Cancelled {merchant} (was {monthly_amount_minor} minor units/month)."


# -- The approval gate -----------------------------------------------------


class SpikeApprovalHook(HookProvider):
    """Interrupts before `cancel_subscription`.

    Stands in for the real `PolicyHook`. A3 replaces the hard-coded tool-name
    check with `policy.evaluate(action, policies)`; the interrupt plumbing here
    is what A3 will keep.
    """

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.gate)

    def gate(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] != "cancel_subscription":
            return

        tool_input = event.tool_use["input"]

        # `reason` must be JSON-serializable — it is persisted in the session and
        # handed back to us verbatim in `result.interrupts[].reason`. This is
        # where the DecisionCard's presentation fields come from.
        reason = {
            "action_id": ACTION_ID,
            "kind": "cancel_subscription",
            "risk": "confirm",
            "merchant": tool_input.get("merchant"),
            "monthly_amount_minor": tool_input.get("monthly_amount_minor"),
            "headline": f"Cancel {tool_input.get('merchant')}?",
            "body": (
                f"{tool_input.get('merchant')} is about to renew at "
                f"{tool_input.get('monthly_amount_minor')} minor units/month."
            ),
            "why_asking": "This cancels a service you pay for, and no rule covers it yet.",
        }

        # First pass: raises InterruptException, unwinds to the event loop, which
        # persists the session and returns stop_reason == "interrupt".
        # Second pass (new process, after resume): returns the stored response.
        answer = event.interrupt(INTERRUPT_NAME, reason=reason)

        log_side_effect(f"GATE resumed with answer={json.dumps(answer, default=str)}")

        if not is_approval(answer):
            event.cancel_tool = "The user declined this action."


def is_approval(answer: Any) -> bool:
    """Interpret the user's answer. Anything unrecognised means no.

    Fail closed: an ambiguous answer must never be read as consent to change a
    service or move money.
    """
    if isinstance(answer, dict):
        choice = answer.get("choice")
    elif isinstance(answer, str):
        choice = answer
    else:
        return False

    return isinstance(choice, str) and choice.strip().casefold() in APPROVING_CHOICES


# -- Agent factory ---------------------------------------------------------


def build_agent() -> Agent:
    """Build the agent. Identical in both processes — that is the whole trick."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    return Agent(
        model=ScriptedModel(
            tool_name="cancel_subscription",
            tool_input={"merchant": MERCHANT, "monthly_amount_minor": MONTHLY_MINOR},
            tool_use_id=TOOL_USE_ID,
            final_text="Subscription request handled.",
        ),
        tools=[cancel_subscription],
        hooks=[SpikeApprovalHook()],
        session_manager=FileSessionManager(
            session_id=SESSION_ID,
            storage_dir=str(SESSION_DIR),
        ),
        system_prompt="You manage household subscriptions.",
        callback_handler=None,
    )
