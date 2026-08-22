"""The policy gate — a Strands hook that governs every tool call.

This is the heart of Quiet Hours. Registering on `BeforeToolCallEvent` means
*every* tool call passes through the gate, including ones the model improvises.
Safety is not something the prompt asks for politely; it is structural.

    low risk, or covered by a rule you granted  -> execute, log it, stay quiet
    anything else                               -> event.interrupt() -> DecisionCard

--------------------------------------------------------------------------------
LANE A: this is a scaffold, not finished code.

Before implementing, verify the current Strands hook and interrupt API — do not
write it from memory, the SDK moves fast. Use the `context7` MCP server against
`/websites/strandsagents`, specifically:

    docs/user-guide/concepts/interrupts
    docs/user-guide/concepts/agents/hooks

Confirm in particular:
  * the exact signature of `event.interrupt(name, reason=...)` and what it returns
  * how `event.cancel_tool` is set to reject a call
  * the shape of the `interruptResponse` payload sent back on resume
  * how `ToolContext` / `invocation_state` surfaces `household_id` inside a hook

Write what you find into `docs/status/PROGRESS_A.md` — Lane B needs the resume
payload shape for `POST /decisions/{id}/respond`.
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from typing import Any

from quiet_hours_contracts import Policy, ProposedAction

from .policy import Verdict

logger = logging.getLogger(__name__)

INTERRUPT_NAME = "qh-approval"
"""Stable interrupt name. Stored on every DecisionCard and echoed back on resume.
Do not change it without a migration — suspended sessions in S3 reference it."""


class PolicyHook:
    """Registers the policy gate on tool calls.

    Should subclass `strands.hooks.HookProvider`. Left unsubclassed here so the
    scaffold imports cleanly before `strands-agents` is installed.
    """

    def __init__(
        self,
        household_id: str,
        policies: list[Policy],
        store: Any,
    ) -> None:
        self.household_id = household_id
        self.policies = policies
        self.store = store
        self.verdicts: list[tuple[ProposedAction, Verdict]] = []
        """Recorded for the run's stats and the autonomy chart."""

    def register_hooks(self, registry: Any, **kwargs: Any) -> None:
        """Attach to BeforeToolCallEvent.

        TODO(Lane A):
            from strands.hooks import BeforeToolCallEvent
            registry.add_callback(BeforeToolCallEvent, self.gate)
        """
        raise NotImplementedError("Lane A: wire to strands.hooks.BeforeToolCallEvent")

    def gate(self, event: Any) -> None:
        """Allow, interrupt, or cancel one tool call.

        Sketch of the finished flow:

            action = self._action_from_tool_use(event.tool_use)
            if action is None:
                return                      # not a governed tool; let it through

            verdict = evaluate(action, self.policies)
            self.verdicts.append((action, verdict))

            if verdict.allow_silently:
                self.store.write_activity(action, verdict, was_autonomous=True)
                return

            card = self.store.create_decision_card(
                action=action,
                why_asking=verdict.reason,     # <- policy.py wrote this for a human
                interrupt_name=INTERRUPT_NAME,
            )
            answer = event.interrupt(INTERRUPT_NAME, reason=card.model_dump(mode="json"))

            # Execution resumes HERE when the user answers, possibly days later,
            # in a different process, rehydrated from the S3 session.
            if not self._is_approval(answer):
                event.cancel_tool = "The user declined this action."

            self.store.resolve_decision(card.decision_id, answer)

        Two things to get right:

        1. `_action_from_tool_use` must map a raw Strands tool_use into a
           `ProposedAction`. Tools that are not governed (pure reads) return None.
        2. The card must be persisted **before** calling `interrupt()`. The
           process may exit inside that call; an unpersisted card is a lost run.
        """
        raise NotImplementedError("Lane A: implement the gate (see docstring)")

    def _action_from_tool_use(self, tool_use: dict[str, Any]) -> ProposedAction | None:
        """Map a tool call to a governed action, or None if it needs no gate."""
        raise NotImplementedError

    @staticmethod
    def _is_approval(answer: Any) -> bool:
        """Interpret the user's response. Anything unrecognised means 'no'.

        Fail closed. An ambiguous answer must never be read as consent to spend
        money.
        """
        raise NotImplementedError
