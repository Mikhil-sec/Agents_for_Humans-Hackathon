"""Tests for the policy engine.

These are the most important tests in the repository. The policy engine is what
stands between an autonomous agent and someone's bank account, and unlike the
rest of the system it is deterministic — so it can be tested exhaustively, and
should be.

Lane A: keep `test_never_auto_cannot_be_policy_approved` passing. If a change
makes it fail, the change is wrong, not the test.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from quiet_hours_contracts import (
    ActionKind,
    Evidence,
    Money,
    Policy,
    PolicyScope,
    ProposedAction,
    RiskTier,
)

from quiet_hours_agent.policy import effective_risk, evaluate, policy_from_decision

NOW = datetime(2026, 8, 21, 7, 0, tzinfo=UTC)


def make_action(
    kind: ActionKind,
    *,
    risk: RiskTier | None = None,
    merchant: str = "FitLife",
    impact_minor: int | None = None,
) -> ProposedAction:
    return ProposedAction(
        action_id="act_1",
        household_id="hh_1",
        run_id="run_1",
        finding_id="fnd_1",
        kind=kind,
        risk=risk or RiskTier.SILENT,
        summary="test action",
        rationale="because",
        params={"merchant": merchant},
        estimated_impact=(
            Money(amount_minor=impact_minor, currency="GBP")
            if impact_minor is not None
            else None
        ),
        evidence=[Evidence(signal_id="sig_1", excerpt="...", source_ref=None)],
        created_at=NOW,
    )


def make_policy(
    *,
    effect: str = "auto_approve",
    scope: PolicyScope = PolicyScope.MERCHANT,
    kind: ActionKind | None = None,
    merchant: str | None = "FitLife",
    max_minor: int | None = None,
    revoked: bool = False,
) -> Policy:
    return Policy(
        policy_id="pol_1",
        household_id="hh_1",
        scope=scope,
        action_kind=kind,
        merchant=merchant,
        category=None,
        max_amount=Money(amount_minor=max_minor) if max_minor is not None else None,
        effect=effect,  # type: ignore[arg-type]
        description="test policy",
        created_at=NOW,
        revoked_at=NOW if revoked else None,
    )


# --------------------------------------------------------------------------
# The guarantee that must never break
# --------------------------------------------------------------------------


def test_never_auto_cannot_be_policy_approved() -> None:
    """No policy, however broad, may auto-approve an irreversible action.

    This is the single hardest guarantee the system makes. It is enforced by
    ordering in `evaluate()`: NEVER_AUTO is rejected before policies are read.
    """
    action = make_action(ActionKind.DISPUTE_CHARGE)

    permissive = [
        make_policy(scope=PolicyScope.GLOBAL, merchant=None),
        make_policy(scope=PolicyScope.MERCHANT, kind=ActionKind.DISPUTE_CHARGE),
        make_policy(scope=PolicyScope.ACTION_KIND, kind=ActionKind.DISPUTE_CHARGE),
    ]

    for policy in permissive:
        verdict = evaluate(action, [policy], now=NOW)
        assert verdict.allow_silently is False
        assert verdict.effective_risk is RiskTier.NEVER_AUTO

    # And with every permissive policy at once.
    assert evaluate(action, permissive, now=NOW).allow_silently is False


def test_close_account_is_never_auto() -> None:
    verdict = evaluate(make_action(ActionKind.CLOSE_ACCOUNT), [], now=NOW)
    assert verdict.allow_silently is False
    assert verdict.effective_risk is RiskTier.NEVER_AUTO


# --------------------------------------------------------------------------
# Risk floors
# --------------------------------------------------------------------------


def test_agent_cannot_lower_risk_below_the_floor() -> None:
    """An agent claiming a payment is 'silent' does not make it so."""
    action = make_action(ActionKind.PAY_BILL, risk=RiskTier.SILENT)
    assert effective_risk(action) is RiskTier.CONFIRM


def test_agent_may_raise_its_own_risk() -> None:
    """Raising is allowed — the agent may know something the table doesn't."""
    action = make_action(ActionKind.SET_REMINDER, risk=RiskTier.CONFIRM)
    assert effective_risk(action) is RiskTier.CONFIRM


# --------------------------------------------------------------------------
# Silent execution
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind", [ActionKind.FILE_RECORD, ActionKind.TAG_MERCHANT, ActionKind.SET_REMINDER]
)
def test_low_risk_actions_run_without_asking(kind: ActionKind) -> None:
    assert evaluate(make_action(kind), [], now=NOW).allow_silently is True


def test_confirm_action_asks_when_no_policy_covers_it() -> None:
    verdict = evaluate(make_action(ActionKind.CANCEL_SUBSCRIPTION), [], now=NOW)
    assert verdict.allow_silently is False
    assert verdict.reason  # must be non-empty; it becomes why_asking


def test_confirm_action_runs_silently_under_a_matching_policy() -> None:
    action = make_action(ActionKind.PAY_BILL, merchant="British Gas", impact_minor=9400)
    policy = make_policy(kind=ActionKind.PAY_BILL, merchant="British Gas", max_minor=15000)

    verdict = evaluate(action, [policy], now=NOW)
    assert verdict.allow_silently is True
    assert verdict.policy_id == "pol_1"


def test_policy_amount_ceiling_is_respected() -> None:
    """A £150 ceiling must not cover a £190 bill."""
    action = make_action(ActionKind.PAY_BILL, merchant="British Gas", impact_minor=19000)
    policy = make_policy(kind=ActionKind.PAY_BILL, merchant="British Gas", max_minor=15000)

    assert evaluate(action, [policy], now=NOW).allow_silently is False


def test_amount_bounded_policy_does_not_match_an_unpriced_action() -> None:
    """Refuse to guess. An amount-bounded rule needs an amount to compare."""
    action = make_action(ActionKind.PAY_BILL, merchant="British Gas", impact_minor=None)
    policy = make_policy(kind=ActionKind.PAY_BILL, merchant="British Gas", max_minor=15000)

    assert evaluate(action, [policy], now=NOW).allow_silently is False


def test_merchant_matching_is_case_insensitive() -> None:
    action = make_action(ActionKind.PAY_BILL, merchant="british gas", impact_minor=100)
    policy = make_policy(kind=ActionKind.PAY_BILL, merchant="British Gas", max_minor=15000)

    assert evaluate(action, [policy], now=NOW).allow_silently is True


def test_policy_for_another_merchant_does_not_match() -> None:
    action = make_action(ActionKind.PAY_BILL, merchant="Thames Water", impact_minor=100)
    policy = make_policy(kind=ActionKind.PAY_BILL, merchant="British Gas", max_minor=15000)

    assert evaluate(action, [policy], now=NOW).allow_silently is False


def test_revoked_policy_stops_applying() -> None:
    action = make_action(ActionKind.PAY_BILL, merchant="British Gas", impact_minor=100)
    policy = make_policy(
        kind=ActionKind.PAY_BILL, merchant="British Gas", max_minor=15000, revoked=True
    )

    assert evaluate(action, [policy], now=NOW).allow_silently is False


def test_auto_deny_beats_auto_approve() -> None:
    """If the user said no, honour it, even alongside a permissive rule."""
    action = make_action(ActionKind.CANCEL_SUBSCRIPTION, merchant="FitLife")
    approve = make_policy(effect="auto_approve", kind=ActionKind.CANCEL_SUBSCRIPTION)
    deny = make_policy(effect="auto_deny", kind=ActionKind.CANCEL_SUBSCRIPTION)

    assert evaluate(action, [approve, deny], now=NOW).allow_silently is False


# --------------------------------------------------------------------------
# Policy creation
# --------------------------------------------------------------------------


def test_created_policy_description_is_human_readable() -> None:
    """The description is shown verbatim to the user before they grant autonomy,
    so it has to read as English."""
    action = make_action(ActionKind.PAY_BILL, merchant="British Gas", impact_minor=15000)

    policy = policy_from_decision(
        action,
        policy_id="pol_new",
        household_id="hh_1",
        decision_id="dec_1",
        approve=True,
        scope=PolicyScope.MERCHANT,
        now=NOW,
    )

    assert policy.effect == "auto_approve"
    assert policy.merchant == "British Gas"
    assert "British Gas" in policy.description
    assert policy.created_from_decision_id == "dec_1"


def test_a_created_policy_actually_permits_the_action_it_came_from() -> None:
    """Round-trip: approving 'always' must genuinely stop the next identical ask.

    If this fails, the autonomy curve never moves and the demo has no story.
    """
    action = make_action(ActionKind.PAY_BILL, merchant="British Gas", impact_minor=9400)
    assert evaluate(action, [], now=NOW).allow_silently is False

    policy = policy_from_decision(
        action,
        policy_id="pol_new",
        household_id="hh_1",
        decision_id="dec_1",
        approve=True,
        scope=PolicyScope.MERCHANT,
        now=NOW,
    )

    assert evaluate(action, [policy], now=NOW).allow_silently is True
