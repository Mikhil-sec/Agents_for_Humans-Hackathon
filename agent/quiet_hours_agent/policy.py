"""The policy engine — decides whether an action executes silently or interrupts.

**This module contains no LLM call, and must never contain one.**

That is a deliberate architectural choice, not an optimisation. Learned autonomy
has to be auditable, explainable and revocable: the user must be able to see every
rule they have granted, why it fired, and revoke it. A model deciding whether it
needs permission is exactly the thing a person would not trust with their bank
account — and a prompt can be argued out of a safety rule, where an `if` statement
cannot.

The model proposes. This module decides. The user governs.

See `docs/status/DECISIONS.md` (2026-08-21) for the full rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from quiet_hours_contracts import (
    DEFAULT_RISK_BY_ACTION,
    RISK_ORDER,
    Policy,
    PolicyScope,
    ProposedAction,
    RiskTier,
)


@dataclass(frozen=True)
class Verdict:
    """The outcome of evaluating one proposed action."""

    allow_silently: bool
    effective_risk: RiskTier
    reason: str
    """Human-readable, and shown to the user. If `allow_silently` is False this
    becomes `DecisionCard.why_asking`, so write it for a person, not a log file."""

    policy_id: str | None = None
    """The policy that permitted a silent execution, if any."""


def effective_risk(action: ProposedAction) -> RiskTier:
    """The risk tier actually applied.

    An agent may *raise* the risk of its own proposal — useful when it has context
    the floor table lacks, e.g. an unusually large bill. It may never lower it
    below the floor for that action kind.
    """
    floor = DEFAULT_RISK_BY_ACTION[action.kind]
    return floor if RISK_ORDER[floor] >= RISK_ORDER[action.risk] else action.risk


def _policy_matches(policy: Policy, action: ProposedAction, category: str | None) -> bool:
    """Whether a policy applies to this action.

    Matching is intentionally narrow. A policy that fires more broadly than the
    user expected is worse than one that fires too rarely — the failure mode of
    over-matching is money moving without consent.
    """
    if not policy.is_active:
        return False

    if policy.action_kind is not None and policy.action_kind != action.kind:
        return False

    if policy.max_amount is not None:
        amount = action.estimated_impact
        if amount is None:
            # No amount to compare against, but the policy is amount-bounded.
            # Refuse to match rather than guess.
            return False
        if amount.currency != policy.max_amount.currency:
            return False
        if abs(amount.amount_minor) > policy.max_amount.amount_minor:
            return False

    match policy.scope:
        case PolicyScope.MERCHANT:
            merchant = action.params.get("merchant")
            return (
                policy.merchant is not None
                and isinstance(merchant, str)
                and merchant.casefold() == policy.merchant.casefold()
            )
        case PolicyScope.CATEGORY:
            return (
                policy.category is not None
                and category is not None
                and category.casefold() == policy.category.casefold()
            )
        case PolicyScope.ACTION_KIND:
            return policy.action_kind is not None  # already compared above
        case PolicyScope.GLOBAL:
            return True

    return False


def evaluate(
    action: ProposedAction,
    policies: list[Policy],
    *,
    category: str | None = None,
    now: datetime | None = None,
) -> Verdict:
    """Decide whether `action` runs silently or raises a decision card.

    The order of these checks is load-bearing. `NEVER_AUTO` is rejected before any
    policy is consulted, so no policy can ever grant it — see
    `test_never_auto_cannot_be_policy_approved`.
    """
    _ = now or datetime.now(UTC)
    risk = effective_risk(action)

    # 1. NEVER_AUTO is absolute. Checked first, before policies, deliberately.
    if risk is RiskTier.NEVER_AUTO:
        return Verdict(
            allow_silently=False,
            effective_risk=risk,
            reason=(
                "This action can't be undone, so Quiet Hours always asks — "
                "no rule can approve it automatically."
            ),
        )

    # 2. An explicit auto-deny beats an auto-approve. The user said no; honour it.
    for policy in policies:
        if policy.effect == "auto_deny" and _policy_matches(policy, action, category):
            return Verdict(
                allow_silently=False,
                effective_risk=risk,
                reason=f"You asked Quiet Hours not to do this: {policy.description}",
                policy_id=policy.policy_id,
            )

    # 3. Low-risk work needs no permission at all. This is the bulk of a run.
    if RISK_ORDER[risk] <= RISK_ORDER[RiskTier.NOTIFY]:
        return Verdict(
            allow_silently=True,
            effective_risk=risk,
            reason="Routine and reversible, so Quiet Hours handled it and logged it.",
        )

    # 4. CONFIRM: silent only if the user granted a matching policy.
    for policy in policies:
        if policy.effect == "auto_approve" and _policy_matches(policy, action, category):
            return Verdict(
                allow_silently=True,
                effective_risk=risk,
                reason=f"Covered by a rule you granted: {policy.description}",
                policy_id=policy.policy_id,
            )

    # 5. Nothing covers it. Ask.
    return Verdict(
        allow_silently=False,
        effective_risk=risk,
        reason=_why_asking(action, risk),
    )


def _why_asking(action: ProposedAction, risk: RiskTier) -> str:
    """Plain-English explanation shown on the decision card.

    This is user-facing copy. It is the difference between an agent that feels
    accountable and one that feels arbitrary, so it is worth writing carefully.
    """
    match action.kind.value:
        case "pay_bill":
            return "This moves money, and you have no rule covering this payment yet."
        case "send_email":
            return "This sends a message as you, so Quiet Hours won't do it unasked."
        case "cancel_subscription" | "downgrade_plan":
            return "This changes a service you pay for, and no rule covers it yet."
        case "reschedule_appointment":
            return "This changes a commitment you made to someone else."
        case _:
            return f"This is a {risk.value} action and no rule covers it yet."


def policy_from_decision(
    action: ProposedAction,
    *,
    policy_id: str,
    household_id: str,
    decision_id: str,
    approve: bool,
    scope: PolicyScope,
    category: str | None = None,
    now: datetime | None = None,
) -> Policy:
    """Build the policy created by an `APPROVE_ALWAYS` / `DENY_ALWAYS` choice.

    The `description` produced here is shown verbatim to the user — both on the
    decision card as `creates_policy_preview` *before* they commit, and afterwards
    on the policies page. Autonomy is never granted invisibly, so this string has
    to be honest and legible.
    """
    merchant = action.params.get("merchant")
    merchant = merchant if isinstance(merchant, str) else None
    verb = "Always" if approve else "Never"

    match scope:
        case PolicyScope.MERCHANT:
            target = merchant or "this merchant"
        case PolicyScope.CATEGORY:
            target = f"anything in {category or 'this category'}"
        case PolicyScope.ACTION_KIND:
            target = "any merchant"
        case _:
            target = "everything"

    bound = ""
    if action.estimated_impact is not None and approve:
        bound = f" up to {action.estimated_impact}"

    description = (f"{verb} {action.kind.value.replace('_', ' ')} for {target}{bound}").strip()

    return Policy(
        policy_id=policy_id,
        household_id=household_id,
        scope=scope,
        action_kind=action.kind,
        merchant=merchant if scope is PolicyScope.MERCHANT else None,
        category=category if scope is PolicyScope.CATEGORY else None,
        max_amount=action.estimated_impact if approve else None,
        effect="auto_approve" if approve else "auto_deny",
        description=description,
        created_from_decision_id=decision_id,
        created_at=now or datetime.now(UTC),
    )
