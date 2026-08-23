"""Reading the world. Deliberately ungoverned.

`load_signals` is **not** named after an `ActionKind`, so `PolicyHook` lets it
straight through. That is correct and intentional: reading a household's own
inbox is the job, it has no external effect, and putting it behind the gate would
mean asking permission to start work.

The rule this follows: *the gate governs actions, not observations.* Anything
added to this module must genuinely observe. The moment a tool here changes
something, it belongs in `actions.py` under an `ActionKind` name instead.

`household_id` comes from `invocation_state`, never from a tool argument. It is a
tenancy boundary, and a model that can pass one is a model that can be talked
into passing someone else's.
"""

from __future__ import annotations

import logging

from strands import tool
from strands.types.tools import ToolContext

from ..signals import load_signals_for, render_signals

logger = logging.getLogger(__name__)


@tool(context=True)
def load_signals(tool_context: ToolContext) -> str:
    """Load today's household signals: bills, charges, emails and calendar items.

    Takes no arguments — it always loads the current household's signals for
    today.
    """
    state = tool_context.invocation_state
    household_id = state.get("household_id")

    if not household_id:
        # Never guess. A run that cannot say whose data it is holding must not
        # load anyone's.
        logger.error("load_signals called with no household_id in invocation_state")
        return "No household is in scope for this run, so no signals were loaded."

    signals = load_signals_for(household_id, mode=state.get("provider_mode"))
    logger.info("load_signals household=%s count=%d", household_id, len(signals))

    # Stash the raw contract objects for the runner. The model gets the rendered
    # text; anything that needs the real `Signal` objects — evidence checking,
    # the store — reads them from here rather than parsing them back out of prose.
    state.setdefault("signals", []).extend(signals)

    return render_signals(signals)


INGEST_TOOLS = [load_signals]
