"""The governed action tools — one per `ActionKind` the graph can perform.

**Every tool here is named exactly after its `ActionKind` value.** That is not a
style choice: `PolicyHook.TOOL_ACTION_KINDS` maps tool name to action kind, so a
tool named after its kind is governed automatically and a tool named anything
else silently is not. Naming is the registration mechanism.

Two kinds deliberately have **no tool at all**:

* `send_email` — the product never sends mail on the user's behalf. `draft_email`
  is the whole story, in mock and live alike. Not having the tool is a stronger
  guarantee than gating it would be.
* `close_account` — irreversible, and nothing in the current graph needs it.

Adding either back is a safety decision, not a feature decision, and belongs in
`docs/status/DECISIONS.md` first.

**Six of these reach Lane C's providers when the providers exist** (A4). The
other five are internal by design — `file_record`, `tag_merchant` and
`update_budget_ledger` have no external effect at all, which is why they are
`SILENT`; `reschedule_appointment` and `dispute_charge` have no provider method
to call yet (see `PROGRESS_A.md` for the two-method ask to Lane C).

Every tool that can reach a provider follows the same shape:

    bundle = get_providers(...)          # None in mock mode until Lane C lands
    if bundle is None: return <in-lane result>
    <call the provider, return what it says>

so mock mode keeps working with zero credentials and nothing here changes when
Lane C's implementation arrives. The gate in front of these is real regardless of
what the body does — which is exactly why it was built first.

`household_id` comes from `invocation_state`, never from a tool argument: it is a
tenancy boundary, and a model that can pass one can be talked into passing
someone else's. That is why the provider-backed tools take `tool_context`.

Every tool takes an optional `rationale`. It is what the user reads on the
decision card when the gate stops the call, so it is worth the tokens: without it
a card can only say that the agent proposed something, not why.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from quiet_hours_contracts import Money
from strands import tool
from strands.types.tools import ToolContext

from ..providers import get_providers

logger = logging.getLogger(__name__)

REMINDER_MINUTES = 15
"""How long a reminder occupies on the calendar. `CalendarProvider` has no
reminder concept, so a reminder is a short event — the closest honest mapping
onto the interface Lane C actually published."""


def _bundle_for(tool_context: ToolContext) -> tuple[Any | None, str | None]:
    """`(providers, household_id)`, either of which may be None.

    A tool with no `household_id` must not act. It is a tenancy boundary, and a
    run that cannot say whose data it is holding has no business touching
    anyone's — the same rule `tools/ingest.py` applies to reading.
    """
    state = tool_context.invocation_state
    household_id = state.get("household_id")
    if not household_id:
        logger.error("governed tool called with no household_id in invocation_state")
        return None, None

    return get_providers(state.get("provider_mode")), household_id


def _parse_when(value: str, *, default: datetime | None = None) -> datetime:
    """An ISO-8601 string from the model, as an aware datetime.

    Defensive because the value comes from a model: a malformed date must degrade
    to something sensible rather than crash a tool that has already passed the
    policy gate and may have been explicitly approved by the user.
    """
    try:
        # Python 3.11+ parses a trailing "Z" natively; the project floor is 3.11.
        parsed = datetime.fromisoformat(value)
    except (ValueError, AttributeError):
        logger.warning("could not parse datetime %r; using default", value)
        return default or datetime.now(UTC)

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# -- SILENT: reversible, no external effect ---------------------------------


@tool
def file_record(merchant: str, note: str = "", rationale: str = "") -> str:
    """File an internal record about a merchant. Reversible, no external effect.

    Args:
        merchant: The merchant the record concerns.
        note: Free-text detail worth keeping.
        rationale: Why this is worth recording, written for the user.
    """
    logger.info("file_record merchant=%s", merchant)
    return f"Filed a record for {merchant}." + (f" Note: {note}" if note else "")


@tool
def tag_merchant(merchant: str, category: str, rationale: str = "") -> str:
    """Categorise a merchant so future runs reason about it correctly.

    Args:
        merchant: The merchant to tag.
        category: The category, e.g. 'energy', 'streaming', 'insurance'.
        rationale: Why this category, written for the user.
    """
    logger.info("tag_merchant merchant=%s category=%s", merchant, category)
    return f"Tagged {merchant} as {category}."


@tool
def update_budget_ledger(merchant: str, amount_minor: int, rationale: str = "") -> str:
    """Record a charge against the household's internal ledger.

    Args:
        merchant: Who charged.
        amount_minor: The amount in minor units (8420 == 84.20).
        rationale: What this entry represents, written for the user.
    """
    logger.info("update_budget_ledger merchant=%s minor=%s", merchant, amount_minor)
    return f"Recorded {amount_minor} minor units against {merchant} in the ledger."


# -- NOTIFY: external, harmless, reversible ---------------------------------


@tool(context=True)
def set_reminder(
    tool_context: ToolContext, subject: str, remind_at: str, rationale: str = ""
) -> str:
    """Set a reminder so something is not forgotten.

    Args:
        subject: What to remind the household about.
        remind_at: When, as an ISO-8601 date or datetime.
        rationale: Why this date, written for the user.
    """
    logger.info("set_reminder subject=%s at=%s", subject, remind_at)
    bundle, household_id = _bundle_for(tool_context)
    if bundle is None:
        return f"Reminder set for {remind_at}: {subject}"

    # `CalendarProvider` has no reminder concept, so a reminder is a short event.
    starts = _parse_when(remind_at)
    bundle.calendar.create_event(
        household_id,
        f"Reminder: {subject}",
        starts,
        starts + timedelta(minutes=REMINDER_MINUTES),
        rationale or None,
    )
    return f"Reminder set for {remind_at}: {subject}"


@tool(context=True)
def add_calendar_event(
    tool_context: ToolContext, title: str, starts_at: str, rationale: str = ""
) -> str:
    """Add an event to the household calendar.

    Args:
        title: The event title.
        starts_at: When it starts, as an ISO-8601 datetime.
        rationale: Why it belongs on the calendar, written for the user.
    """
    logger.info("add_calendar_event title=%s at=%s", title, starts_at)
    bundle, household_id = _bundle_for(tool_context)
    if bundle is None:
        return f"Added '{title}' to the calendar for {starts_at}."

    starts = _parse_when(starts_at)
    event_id = bundle.calendar.create_event(
        household_id, title, starts, starts + timedelta(hours=1), rationale or None
    )
    return f"Added '{title}' to the calendar for {starts_at} (event {event_id})."


@tool(context=True)
def draft_email(
    tool_context: ToolContext, recipient: str, subject: str, body: str, rationale: str = ""
) -> str:
    """Write an email draft and leave it for the user. **Never sends.**

    `EmailProvider` has `create_draft` and deliberately has no `send`. The absence
    of the method is the guarantee — this tool could not send if it wanted to.

    Args:
        recipient: Who it is addressed to.
        subject: The subject line.
        body: The message body.
        rationale: Why this needs sending, written for the user.
    """
    logger.info("draft_email recipient=%s subject=%s", recipient, subject)
    bundle, household_id = _bundle_for(tool_context)
    if bundle is None:
        return (
            f"Drafted an email to {recipient} — '{subject}' ({len(body)} characters). "
            "Saved as a draft; nothing was sent."
        )

    draft_id = bundle.email.create_draft(household_id, recipient, subject, body)
    return (
        f"Drafted an email to {recipient} — '{subject}' (draft {draft_id}). "
        "Saved as a draft; nothing was sent."
    )


# -- CONFIRM: money, messages, or a change to a service ---------------------


@tool(context=True)
def pay_bill(
    tool_context: ToolContext,
    merchant: str,
    amount_minor: int,
    due_date: str = "",
    rationale: str = "",
) -> str:
    """Schedule a bill payment. Creates a **payment request**, never a transfer.

    Args:
        merchant: Who to pay.
        amount_minor: How much, in minor units (8420 == 84.20).
        due_date: When it is due, as an ISO-8601 date.
        rationale: Why this should be paid, written for the user.
    """
    logger.info("pay_bill merchant=%s minor=%s", merchant, amount_minor)
    bundle, household_id = _bundle_for(tool_context)
    if bundle is None:
        return (
            f"Scheduled a payment request of {amount_minor} minor units to {merchant}"
            + (f", due {due_date}" if due_date else "")
            + ". No money has moved."
        )

    # `schedule_payment` creates a *request* a human confirms out of band. There
    # is no method on `PaymentProvider` that moves money unattended, and none may
    # be added — see `integrations/base.py`.
    payment_id = bundle.payments.schedule_payment(
        household_id,
        merchant,
        Money(amount_minor=amount_minor, currency="GBP"),
        _parse_when(due_date, default=datetime.now(UTC) + timedelta(days=7)),
        rationale or None,
    )
    return (
        f"Scheduled a payment request of {amount_minor} minor units to {merchant}"
        + (f", due {due_date}" if due_date else "")
        + f" (request {payment_id}). No money has moved."
    )


@tool(context=True)
def cancel_subscription(
    tool_context: ToolContext,
    merchant: str,
    monthly_amount_minor: int,
    reason: str = "",
    rationale: str = "",
) -> str:
    """Cancel a recurring subscription.

    Args:
        merchant: The service to cancel.
        monthly_amount_minor: Current monthly charge in minor units (3800 == 38.00).
        reason: Why it is being cancelled, in the household's own terms.
        rationale: Why the agent believes this, written for the user.
    """
    logger.info("cancel_subscription merchant=%s minor=%s", merchant, monthly_amount_minor)
    bundle, household_id = _bundle_for(tool_context)
    if bundle is None:
        return (
            f"Cancellation recorded for {merchant} "
            f"(was {monthly_amount_minor} minor units/month)."
            + (f" Reason: {reason}" if reason else "")
        )

    receipt = bundle.subscriptions.cancel(household_id, merchant, reason or None)
    return (
        f"Cancelled {merchant} (was {monthly_amount_minor} minor units/month). "
        f"Receipt {receipt}." + (f" Reason: {reason}" if reason else "")
    )


@tool(context=True)
def downgrade_plan(
    tool_context: ToolContext,
    merchant: str,
    to_plan: str,
    monthly_amount_minor: int = 0,
    from_plan: str = "",
    rationale: str = "",
) -> str:
    """Move a subscription to a cheaper tier instead of cancelling it.

    Args:
        merchant: The service to change.
        to_plan: The plan to move to.
        monthly_amount_minor: The new monthly charge in minor units.
        from_plan: The plan they are on now.
        rationale: Why this tier suits them better, written for the user.
    """
    logger.info("downgrade_plan merchant=%s to=%s", merchant, to_plan)
    described = (
        f"{merchant}"
        + (f": {from_plan} -> {to_plan}" if from_plan else f" to {to_plan}")
        + (f" ({monthly_amount_minor} minor units/month)" if monthly_amount_minor else "")
    )

    bundle, household_id = _bundle_for(tool_context)
    if bundle is None:
        return f"Plan change recorded for {described}."

    receipt = bundle.subscriptions.downgrade(household_id, merchant, to_plan)
    return f"Plan changed for {described}. Receipt {receipt}."


@tool
def reschedule_appointment(
    merchant: str, to_datetime: str, from_datetime: str = "", rationale: str = ""
) -> str:
    """Move an existing appointment.

    Args:
        merchant: Who the appointment is with.
        to_datetime: The new time, as an ISO-8601 datetime.
        from_datetime: The time it is currently booked for.
        rationale: Why it needs moving, written for the user.
    """
    logger.info("reschedule_appointment merchant=%s to=%s", merchant, to_datetime)
    return (
        f"Reschedule requested with {merchant}"
        + (f" from {from_datetime}" if from_datetime else "")
        + f" to {to_datetime}."
    )


# -- NEVER_AUTO: irreversible or high value ---------------------------------


@tool
def dispute_charge(merchant: str, amount_minor: int, reason: str, rationale: str = "") -> str:
    """Formally dispute a charge with the provider.

    Irreversible and consequential, so it always asks the user — no learned
    policy can ever auto-approve it. See `policy.evaluate`.

    Args:
        merchant: Who made the charge.
        amount_minor: The disputed amount in minor units.
        reason: The grounds for the dispute.
        rationale: Why the agent believes this is wrong, written for the user.
    """
    logger.info("dispute_charge merchant=%s minor=%s", merchant, amount_minor)
    return f"Dispute prepared against {merchant} for {amount_minor} minor units. Grounds: {reason}"


BILL_TOOLS = [file_record, tag_merchant, update_budget_ledger, pay_bill, dispute_charge]
"""What the bill analyst may do."""

NEGOTIATION_TOOLS = [cancel_subscription, downgrade_plan, draft_email, file_record]
"""What the negotiator may do."""

SCHEDULING_TOOLS = [set_reminder, add_calendar_event, reschedule_appointment]
"""What the scheduler may do."""

ACTION_TOOLS = [
    file_record,
    tag_merchant,
    update_budget_ledger,
    set_reminder,
    add_calendar_event,
    draft_email,
    pay_bill,
    cancel_subscription,
    downgrade_plan,
    reschedule_appointment,
    dispute_charge,
]
"""Every governed tool, for tests that assert the naming convention holds."""
