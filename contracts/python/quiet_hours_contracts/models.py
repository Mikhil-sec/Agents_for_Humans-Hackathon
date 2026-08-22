"""Shared data models for Quiet Hours.

FROZEN from 2026-08-24. Changes require a `contract:` PR with two approvals.
See docs/CONTRACTS.md.

Design notes that are load-bearing — please read before extending:

* **Money is an integer count of minor units** (pence, cents) plus an ISO-4217
  currency code. Never a float. `Money(amount_minor=1799, currency="GBP")` is
  17.99. Formatting for display is the web layer's job.
* **Every timestamp is timezone-aware UTC.** The user's local timezone lives on
  `Household.timezone` and is applied at render time only.
* **IDs are opaque strings.** Do not parse them. They are ULIDs in practice, but
  no consumer may rely on that.
* **The wire format is snake_case.** TypeScript consumers map it in
  `contracts/typescript/`. Do not add camelCase aliases here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    ActionKind,
    DecisionChoice,
    DecisionStatus,
    FindingKind,
    PolicyScope,
    RiskTier,
    RunStatus,
    RunTrigger,
    SignalKind,
)
from .version import CONTRACT_VERSION


class _Base(BaseModel):
    """Common config for every contract model."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        use_enum_values=False,
        ser_json_timedelta="iso8601",
    )


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------


class Money(_Base):
    """An exact monetary amount. Integer minor units only — never a float."""

    amount_minor: int = Field(description="Amount in minor units. 1799 == 17.99")
    currency: str = Field(default="GBP", min_length=3, max_length=3)

    def __str__(self) -> str:
        return f"{self.currency} {self.amount_minor / 100:.2f}"


class Evidence(_Base):
    """A pointer back to the raw material that justified a conclusion.

    Every finding and every proposed action must carry at least one. This is what
    makes the activity trail auditable, and it is a hard product requirement:
    the user must always be able to ask "why did you think that?".
    """

    signal_id: str
    excerpt: str = Field(max_length=500, description="Human-readable snippet, redacted")
    source_ref: str | None = Field(
        default=None, description="Provider-specific locator, e.g. a Gmail message id"
    )


# --------------------------------------------------------------------------
# Household / user configuration
# --------------------------------------------------------------------------


class Household(_Base):
    """The unit Quiet Hours works on behalf of. One per deployment in the demo."""

    household_id: str
    display_name: str
    timezone: str = Field(default="Europe/London", description="IANA tz name")
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    digest_hour_local: int = Field(default=8, ge=0, le=23)
    quiet_hours_local: tuple[int, int] = Field(
        default=(22, 7),
        description="Start and end hour during which the agent never notifies.",
    )
    created_at: datetime


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------


class Signal(_Base):
    """One raw item pulled from a provider. Uninterpreted."""

    signal_id: str
    household_id: str
    kind: SignalKind
    occurred_at: datetime
    ingested_at: datetime
    source: str = Field(description="Provider name, e.g. 'gmail', 'mock_bank'")

    subject: str | None = None
    body: str | None = None
    merchant: str | None = None
    amount: Money | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Reasoning output
# --------------------------------------------------------------------------


class Finding(_Base):
    """What the triage and analysis agents concluded.

    A finding is a *belief*, not an action. It may produce zero, one or several
    proposed actions.
    """

    finding_id: str
    household_id: str
    run_id: str
    kind: FindingKind
    title: str = Field(max_length=120, description="One line, user-facing")
    detail: str = Field(description="A short paragraph, user-facing")
    confidence: float = Field(ge=0.0, le=1.0)
    merchant: str | None = None
    category: str | None = None
    amount: Money | None = None
    previous_amount: Money | None = Field(
        default=None, description="For price increases: what it used to be"
    )
    due_at: datetime | None = None
    evidence: list[Evidence] = Field(min_length=1)
    created_at: datetime


class ProposedAction(_Base):
    """Something the agent intends to do. May execute silently or become a card.

    `risk` is the tier the *agent* assigned. The policy engine recomputes the
    effective tier as `max(DEFAULT_RISK_BY_ACTION[kind], risk)` — an agent can
    raise its own risk assessment but never lower it below the floor.
    """

    action_id: str
    household_id: str
    run_id: str
    finding_id: str
    kind: ActionKind
    risk: RiskTier
    summary: str = Field(max_length=160, description="One line: 'Cancel FitLife (£38/mo)'")
    rationale: str = Field(description="Why the agent wants to do this. Shown to the user.")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific payload. Shape is owned by the tool that consumes it.",
    )
    reversible: bool = True
    estimated_impact: Money | None = Field(
        default=None, description="Money saved (positive) or spent (negative) per year"
    )
    evidence: list[Evidence] = Field(min_length=1)
    created_at: datetime


# --------------------------------------------------------------------------
# The interrupt surface — the heart of the product
# --------------------------------------------------------------------------


class DecisionOption(_Base):
    """One button on a decision card."""

    choice: DecisionChoice
    label: str = Field(max_length=48, description="Button text, e.g. 'Cancel it'")
    description: str | None = Field(
        default=None, max_length=160, description="Sub-label explaining the consequence"
    )
    is_default: bool = False
    creates_policy_preview: str | None = Field(
        default=None,
        description=(
            "For APPROVE_ALWAYS / DENY_ALWAYS: the rule this would create, in plain "
            "English, e.g. 'Always auto-pay British Gas under £150'. Shown to the user "
            "before they commit, so autonomy is never granted invisibly."
        ),
    )


class DecisionCard(_Base):
    """A question the agent has stopped to ask.

    Created when the policy engine declines to auto-approve a proposed action.
    Carries the Strands interrupt identifiers needed to resume the suspended run.
    """

    decision_id: str
    household_id: str
    run_id: str
    action_id: str

    # --- Strands interrupt linkage. Owned by Lane A; opaque to Lanes B and C. --
    session_id: str = Field(description="Strands SessionManager session id")
    interrupt_id: str = Field(description="Strands interrupt id, echoed back on resume")
    interrupt_name: str = Field(description="Strands interrupt name, e.g. 'qh-approval'")

    # --- Presentation ------------------------------------------------------
    headline: str = Field(max_length=120, description="'FitLife is about to charge you £38'")
    body: str = Field(description="A short paragraph of context")
    why_asking: str = Field(
        max_length=240,
        description=(
            "Why this needed a human. e.g. 'This cancels a service, and you have no "
            "policy covering fitness subscriptions.' Required — it is what makes the "
            "agent feel accountable rather than arbitrary."
        ),
    )
    options: list[DecisionOption] = Field(min_length=2)
    amount: Money | None = None
    estimated_impact: Money | None = None
    evidence: list[Evidence] = Field(min_length=1)

    status: DecisionStatus = DecisionStatus.PENDING
    urgency_deadline: datetime | None = Field(
        default=None, description="After this the opportunity is lost, e.g. the trial converts"
    )
    created_at: datetime
    resolved_at: datetime | None = None


class DecisionResponse(_Base):
    """The user's answer. Posted by the web app; consumed by the agent on resume."""

    decision_id: str
    choice: DecisionChoice
    edited_params: dict[str, Any] | None = Field(
        default=None, description="Present only when choice == EDIT"
    )
    snooze_until: datetime | None = Field(
        default=None, description="Present only when choice == SNOOZE"
    )
    note: str | None = Field(default=None, max_length=500)
    responded_at: datetime


# --------------------------------------------------------------------------
# Learned autonomy
# --------------------------------------------------------------------------


class Policy(_Base):
    """A rule the agent learned from the user's answers.

    Policies are how the interrupt rate falls over time. They are always created
    from an explicit user choice (`APPROVE_ALWAYS` / `DENY_ALWAYS`) or written by
    hand on the policies page — **never inferred silently by the model.**
    """

    policy_id: str
    household_id: str
    scope: PolicyScope
    action_kind: ActionKind | None = None
    merchant: str | None = None
    category: str | None = None
    max_amount: Money | None = Field(
        default=None, description="Auto-approve only at or below this amount"
    )
    effect: Literal["auto_approve", "auto_deny"]
    description: str = Field(
        max_length=200, description="Plain English. Shown verbatim on the policies page."
    )

    created_from_decision_id: str | None = None
    created_at: datetime
    revoked_at: datetime | None = None
    times_applied: int = 0
    last_applied_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


# --------------------------------------------------------------------------
# Runs and audit trail
# --------------------------------------------------------------------------


class ActivityEntry(_Base):
    """One line in the audit trail. Written for every action the agent takes,
    silent or not. This is a hard requirement — nothing happens invisibly."""

    entry_id: str
    household_id: str
    run_id: str
    action_id: str | None = None
    decision_id: str | None = None
    occurred_at: datetime

    summary: str = Field(max_length=160)
    rationale: str
    risk: RiskTier
    was_autonomous: bool = Field(description="True if executed without asking the user")
    policy_id: str | None = Field(
        default=None, description="The policy that permitted an autonomous action, if any"
    )
    succeeded: bool = True
    error: str | None = None
    impact: Money | None = None


class RunStats(_Base):
    """The numbers behind the demo's headline chart."""

    signals_ingested: int = 0
    findings_created: int = 0
    actions_proposed: int = 0
    actions_autonomous: int = 0
    decisions_raised: int = 0
    policies_applied: int = 0
    estimated_annual_savings: Money | None = None

    @property
    def autonomy_rate(self) -> float:
        """Share of actions handled without interrupting the user. The metric the
        whole product is optimising for."""
        if self.actions_proposed == 0:
            return 1.0
        return self.actions_autonomous / self.actions_proposed


class Run(_Base):
    """One execution of the agent, from wake-up to digest.

    A run that hits an interrupt goes to `WAITING_ON_USER` and its Strands session
    is persisted. It resumes — as the same `run_id` — whenever the user answers,
    which may be days later.
    """

    run_id: str
    household_id: str
    trigger: RunTrigger
    status: RunStatus
    session_id: str
    started_at: datetime
    finished_at: datetime | None = None
    stats: RunStats = Field(default_factory=RunStats)
    error: str | None = None


class DailyBrief(_Base):
    """What the user actually receives. Usually short. Sometimes empty."""

    brief_id: str
    household_id: str
    run_id: str
    generated_at: datetime
    headline: str = Field(
        max_length=120,
        description="'Nothing needs you today' is a valid and common headline.",
    )
    handled_silently: list[str] = Field(
        default_factory=list, description="One line per autonomous action"
    )
    pending_decision_ids: list[str] = Field(default_factory=list)
    savings_this_month: Money | None = None
    autonomy_rate: float = Field(ge=0.0, le=1.0, default=1.0)


# --------------------------------------------------------------------------
# API envelopes
# --------------------------------------------------------------------------


class ApiError(_Base):
    """Every non-2xx response body has this shape."""

    error: str = Field(description="Stable machine-readable code, e.g. 'decision_not_found'")
    message: str = Field(description="Human-readable detail")
    contract_version: str = CONTRACT_VERSION


class Page(_Base):
    """Cursor pagination envelope. `items` is typed by the endpoint."""

    items: list[Any]
    next_cursor: str | None = None
    contract_version: str = CONTRACT_VERSION
