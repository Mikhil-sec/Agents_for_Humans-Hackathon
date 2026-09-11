"""Shared enumerations for Quiet Hours.

FROZEN from 2026-08-24. Changes require a `contract:` PR with two approvals.
See docs/CONTRACTS.md.

Every value here is part of the wire format. Renaming a member is a breaking
change even if the Python identifier stays the same.
"""

from __future__ import annotations

from enum import Enum


class ProviderMode(str, Enum):
    """How the agent reaches the outside world.

    `MOCK` must always work with zero credentials — it is how judges run us.
    """

    MOCK = "mock"
    LIVE = "live"


class SignalKind(str, Enum):
    """A raw item ingested from a provider, before any interpretation."""

    EMAIL = "email"
    TRANSACTION = "transaction"
    CALENDAR_EVENT = "calendar_event"
    STATEMENT = "statement"


class FindingKind(str, Enum):
    """What triage concluded about one or more signals.

    This is the vocabulary of household admin. Adding a member here is the most
    likely legitimate contract change during the build — it is additive and safe
    for existing consumers, but still requires a `contract:` PR.
    """

    BILL_DUE = "bill_due"
    PRICE_INCREASE = "price_increase"
    TRIAL_CONVERTING = "trial_converting"
    DUPLICATE_SERVICE = "duplicate_service"
    UNUSED_SUBSCRIPTION = "unused_subscription"
    UNEXPECTED_CHARGE = "unexpected_charge"
    RENEWAL_UPCOMING = "renewal_upcoming"
    APPOINTMENT_NEEDS_REPLY = "appointment_needs_reply"
    USAGE_ANOMALY = "usage_anomaly"
    NOTHING_TO_DO = "nothing_to_do"


class ActionKind(str, Enum):
    """Something the agent can actually do about a finding."""

    # Silent, internal-only
    FILE_RECORD = "file_record"
    TAG_MERCHANT = "tag_merchant"
    UPDATE_BUDGET_LEDGER = "update_budget_ledger"

    # Notify — external but harmless and reversible
    SET_REMINDER = "set_reminder"
    ADD_CALENDAR_EVENT = "add_calendar_event"

    # Confirm — money, messages, or service changes
    PAY_BILL = "pay_bill"
    DRAFT_EMAIL = "draft_email"
    SEND_EMAIL = "send_email"
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    DOWNGRADE_PLAN = "downgrade_plan"
    RESCHEDULE_APPOINTMENT = "reschedule_appointment"

    # Never auto — irreversible or high value
    DISPUTE_CHARGE = "dispute_charge"
    CLOSE_ACCOUNT = "close_account"


class RiskTier(str, Enum):
    """Governs whether an action interrupts the user.

    The ordering matters: see `RISK_ORDER` below.
    """

    SILENT = "silent"
    """Reversible, no external effect. Executes without asking. Always logged."""

    NOTIFY = "notify"
    """External but harmless and reversible. Executes; appears in the digest."""

    CONFIRM = "confirm"
    """Spends money, sends a message, or changes a service. Interrupts unless a
    learned policy explicitly permits this exact case."""

    NEVER_AUTO = "never_auto"
    """Irreversible or high value. Always interrupts. No policy may auto-approve
    it — this is enforced in the policy engine, not left to the model."""


RISK_ORDER: dict[RiskTier, int] = {
    RiskTier.SILENT: 0,
    RiskTier.NOTIFY: 1,
    RiskTier.CONFIRM: 2,
    RiskTier.NEVER_AUTO: 3,
}
"""Comparable severity. Higher is stricter. Used by the policy engine."""


DEFAULT_RISK_BY_ACTION: dict[ActionKind, RiskTier] = {
    ActionKind.FILE_RECORD: RiskTier.SILENT,
    ActionKind.TAG_MERCHANT: RiskTier.SILENT,
    ActionKind.UPDATE_BUDGET_LEDGER: RiskTier.SILENT,
    ActionKind.SET_REMINDER: RiskTier.NOTIFY,
    ActionKind.ADD_CALENDAR_EVENT: RiskTier.NOTIFY,
    ActionKind.PAY_BILL: RiskTier.CONFIRM,
    ActionKind.DRAFT_EMAIL: RiskTier.NOTIFY,
    ActionKind.SEND_EMAIL: RiskTier.CONFIRM,
    ActionKind.CANCEL_SUBSCRIPTION: RiskTier.CONFIRM,
    ActionKind.DOWNGRADE_PLAN: RiskTier.CONFIRM,
    ActionKind.RESCHEDULE_APPOINTMENT: RiskTier.CONFIRM,
    ActionKind.DISPUTE_CHARGE: RiskTier.NEVER_AUTO,
    ActionKind.CLOSE_ACCOUNT: RiskTier.NEVER_AUTO,
}
"""The floor risk for each action kind.

An action's effective risk is `max(DEFAULT_RISK_BY_ACTION[kind], proposed_risk)`.
An agent may raise the risk of its own proposal; it may never lower it.
"""


class DecisionStatus(str, Enum):
    """Lifecycle of a decision card."""

    PENDING = "pending"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"
    """The situation resolved itself before the user answered (e.g. the user
    cancelled the subscription manually)."""


class DecisionChoice(str, Enum):
    """What the user said."""

    APPROVE = "approve"
    APPROVE_ALWAYS = "approve_always"
    """Approve, and create a policy so this class of action never asks again."""

    EDIT = "edit"
    """Approve a modified version of the proposed action."""

    DENY = "deny"
    DENY_ALWAYS = "deny_always"
    """Deny, and create a policy suppressing this class of proposal."""

    SNOOZE = "snooze"


class RunStatus(str, Enum):
    """Lifecycle of one agent run."""

    RUNNING = "running"
    WAITING_ON_USER = "waiting_on_user"
    """The Strands session is suspended at an interrupt. It will resume when the
    user answers — possibly days later."""

    COMPLETED = "completed"
    FAILED = "failed"


class RunTrigger(str, Enum):
    SCHEDULE = "schedule"
    MANUAL = "manual"
    RESUME = "resume"
    """Re-entry after a user answered a decision card."""


class PolicyScope(str, Enum):
    """How broadly a learned policy applies."""

    MERCHANT = "merchant"
    """This merchant only, e.g. 'auto-pay British Gas'."""

    CATEGORY = "category"
    """A spending category, e.g. 'never auto-renew fitness'."""

    ACTION_KIND = "action_kind"
    """Any occurrence of an action kind, e.g. 'always file records silently'."""

    GLOBAL = "global"
    """Applies everywhere, e.g. 'always ask above 50.00'."""
