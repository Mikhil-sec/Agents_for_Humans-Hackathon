"""Structured output schemas for the graph nodes.

These are the `structured_output_model` types handed to each agent, and they are
deliberately *not* the contract models from `quiet_hours_contracts`.

**Why not just ask for a `Finding`?** Because a contract `Finding` carries
`finding_id`, `household_id`, `run_id` and `created_at`, and none of those are
the model's to decide:

* ids and timestamps are identity — generating them in the model makes them
  non-deterministic, unverifiable, and occasionally duplicated;
* `household_id` is a **tenancy boundary**. A model that can emit one is a model
  that can be talked into emitting someone else's, and every downstream query is
  scoped by it. It is set by the runner from `invocation_state`, never inferred.

So the model fills in the part that needs judgement, and `graph.py` promotes each
draft into the real contract object with identity it owns. That split is also why
these schemas can stay small: small schemas produce better structured output, and
they cost fewer tokens on every node in every run.

The mapping functions live here too, next to the shapes they map, so a change to
one is a change to the other in the same diff.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from quiet_hours_contracts import (
    ActionKind,
    Evidence,
    Finding,
    FindingKind,
    Money,
    ProposedAction,
    RiskTier,
)


class _Draft(BaseModel):
    """Base for everything a model is asked to produce.

    `extra="ignore"` on purpose: a model that volunteers an extra key should not
    fail the whole run, it should just not be believed.
    """

    model_config = ConfigDict(extra="ignore")


class DraftEvidence(_Draft):
    """A citation back to a signal the node was actually shown."""

    signal_id: str = Field(description="The id of a signal from the input. Never invent one.")
    excerpt: str = Field(
        max_length=500, description="A short quote from that signal, not a paraphrase."
    )


class DraftFinding(_Draft):
    """One belief about the household's admin. Not yet an action."""

    kind: FindingKind
    title: str = Field(max_length=120, description="One line a person would recognise")
    detail: str = Field(description="A short paragraph, written to the user")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[DraftEvidence] = Field(min_length=1)

    merchant: str | None = None
    category: str | None = Field(
        default=None, description="e.g. 'energy', 'streaming', 'insurance'"
    )
    amount_minor: int | None = Field(
        default=None, description="Integer minor units. 1799 == 17.99. Never a decimal."
    )
    previous_amount_minor: int | None = Field(
        default=None, description="For a price increase: what it used to be, in minor units"
    )
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    due_at: datetime | None = None


class TriageResult(_Draft):
    """Everything triage concluded about today's signals."""

    findings: list[DraftFinding] = Field(
        default_factory=list,
        description="May be empty. An empty result is a good day, not a failure.",
    )


class DraftAction(_Draft):
    """Something a specialist did, or wants to do, about a finding."""

    kind: ActionKind
    summary: str = Field(max_length=160, description="One line: 'Cancel FitLife (GBP 38.00/mo)'")
    rationale: str = Field(description="Why. Written to the user — they will read this verbatim.")
    evidence: list[DraftEvidence] = Field(min_length=1)

    risk: RiskTier = Field(
        default=RiskTier.CONFIRM,
        description=(
            "Your own read of how sensitive this is. The gate takes the stricter of "
            "this and the floor for the action kind, so raising it works and "
            "lowering it does nothing."
        ),
    )
    finding_id: str | None = Field(
        default=None, description="The finding this came from, if it came from one"
    )
    merchant: str | None = None
    reversible: bool = True
    estimated_impact_minor: int | None = Field(
        default=None,
        description="Money saved per year (positive) or spent (negative), in minor units",
    )
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    params: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Action-specific payload for the tool that carries it out",
    )


class ActionPlan(_Draft):
    """What one specialist proposes. May legitimately be empty."""

    actions: list[DraftAction] = Field(default_factory=list)
    note: str = Field(default="", description="At most a sentence, only if something needs saying")


class BriefDraft(_Draft):
    """The short note the household reads."""

    headline: str = Field(
        max_length=120,
        description="'Nothing needs you today' is a valid and common headline",
    )
    handled_silently: list[str] = Field(
        default_factory=list, description="One past-tense line per autonomous action"
    )
    note: str = Field(default="", description="At most a sentence or two. Usually empty.")


# --------------------------------------------------------------------------
# Promotion into contract objects
#
# The model supplies judgement; these functions supply identity. Nothing here
# reads anything the model produced when deciding `household_id` or `run_id`.
# --------------------------------------------------------------------------


def _money(amount_minor: int | None, currency: str) -> Money | None:
    return None if amount_minor is None else Money(amount_minor=amount_minor, currency=currency)


def _evidence(items: list[DraftEvidence]) -> list[Evidence]:
    return [Evidence(signal_id=item.signal_id, excerpt=item.excerpt) for item in items]


def finding_from_draft(
    draft: DraftFinding,
    *,
    finding_id: str,
    household_id: str,
    run_id: str,
    created_at: datetime,
) -> Finding:
    """Promote a `DraftFinding` into a contract `Finding`."""
    return Finding(
        finding_id=finding_id,
        household_id=household_id,
        run_id=run_id,
        kind=draft.kind,
        title=draft.title,
        detail=draft.detail,
        confidence=draft.confidence,
        merchant=draft.merchant,
        category=draft.category,
        amount=_money(draft.amount_minor, draft.currency),
        previous_amount=_money(draft.previous_amount_minor, draft.currency),
        due_at=draft.due_at,
        evidence=_evidence(draft.evidence),
        created_at=created_at,
    )


def action_from_draft(
    draft: DraftAction,
    *,
    action_id: str,
    household_id: str,
    run_id: str,
    created_at: datetime,
    fallback_finding_id: str = "unbacked",
) -> ProposedAction:
    """Promote a `DraftAction` into a contract `ProposedAction`.

    `risk` is passed through exactly as the model set it. It is not clamped here
    on purpose — `policy.effective_risk` applies the floor, and keeping that in
    one place is what makes the guarantee testable.
    """
    params = {key: value for key, value in draft.params.items() if value is not None}
    if draft.merchant and "merchant" not in params:
        params["merchant"] = draft.merchant

    return ProposedAction(
        action_id=action_id,
        household_id=household_id,
        run_id=run_id,
        finding_id=draft.finding_id or fallback_finding_id,
        kind=draft.kind,
        risk=draft.risk,
        summary=draft.summary,
        rationale=draft.rationale,
        params=params,
        reversible=draft.reversible,
        estimated_impact=_money(draft.estimated_impact_minor, draft.currency),
        evidence=_evidence(draft.evidence),
        created_at=created_at,
    )
