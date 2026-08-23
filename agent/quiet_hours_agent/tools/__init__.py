"""Agent tools, split by whether the policy gate governs them.

Tool *names* are load-bearing. A tool named exactly like an `ActionKind` value is
automatically governed by `PolicyHook` (see `TOOL_ACTION_KINDS` in `hooks.py`);
a tool named anything else passes through ungoverned. So:

* `actions.py` — every governed tool, each named after its `ActionKind`.
* `ingest.py`  — observation only, deliberately outside the gate.

Name a new action tool after its kind and it is governed for free. Name it
something else and it is an ungoverned path to someone's bank account. That is
the one thing to get right in this package.
"""

from .actions import (
    ACTION_TOOLS,
    BILL_TOOLS,
    NEGOTIATION_TOOLS,
    SCHEDULING_TOOLS,
    add_calendar_event,
    cancel_subscription,
    dispute_charge,
    downgrade_plan,
    draft_email,
    file_record,
    pay_bill,
    reschedule_appointment,
    set_reminder,
    tag_merchant,
    update_budget_ledger,
)
from .ingest import INGEST_TOOLS, load_signals

DEMO_TOOLS = [file_record, cancel_subscription]
"""The A1/A3 pair — one either side of the gate.

Kept because it is the smallest thing that demonstrates the whole product thesis,
and because the interrupt spikes are pinned to it.
"""

__all__ = [
    "ACTION_TOOLS",
    "BILL_TOOLS",
    "DEMO_TOOLS",
    "INGEST_TOOLS",
    "NEGOTIATION_TOOLS",
    "SCHEDULING_TOOLS",
    "add_calendar_event",
    "cancel_subscription",
    "dispute_charge",
    "downgrade_plan",
    "draft_email",
    "file_record",
    "load_signals",
    "pay_bill",
    "reschedule_appointment",
    "set_reminder",
    "tag_merchant",
    "update_budget_ledger",
]
