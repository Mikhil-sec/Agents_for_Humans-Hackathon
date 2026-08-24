"""A6 — the autonomy curve.

The curve is the demo's centrepiece, so the tests that matter here are the ones
that prove it is **measured rather than authored**:

* `test_the_curve_is_flat_when_the_user_never_teaches_a_rule` — same four weeks,
  same actions, answered with `APPROVE` instead of `APPROVE_ALWAYS`. If the
  numbers were coming from `replay.py`'s data they would be identical. They are
  not, because they come from `policy.py`.
* `test_every_scenario_action_is_routed_to_a_node_that_owns_it` — the silent
  failure this file exists to prevent. A finding kind that wakes the wrong
  specialist means the action never runs, and the week simply looks quieter than
  it is. That bug shipped once and produced a fake 100% week.
* `test_an_interrupted_action_is_counted_once` — the gate runs twice for anything
  that interrupts, so a naive count deflates the very metric being reported.
"""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

import pytest
from quiet_hours_contracts import ActionKind, DecisionChoice, RiskTier

from quiet_hours_agent.replay import WEEKS, ReplayResult, WeekResult, render, replay
from quiet_hours_agent.scenarios import NODE_TOOLS, ScenarioStats
from quiet_hours_agent.store import JsonStore

HOUSEHOLD = "hh_demo"


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("QH_PROVIDER_MODE", "mock")


@pytest.fixture
def store(tmp_path) -> JsonStore:
    return JsonStore(tmp_path / "store")


def run_replay(store, tmp_path, *, answer=DecisionChoice.APPROVE_ALWAYS, weeks=None):
    return replay(
        HOUSEHOLD,
        store=store,
        session_dir=tmp_path / "sessions",
        weeks=weeks or WEEKS,
        answer=answer,
        start=datetime(2026, 8, 1, tzinfo=UTC),
    )


# --------------------------------------------------------------------------
# The curve
# --------------------------------------------------------------------------


def test_the_autonomy_curve_rises_across_four_weeks(store, tmp_path):
    result = run_replay(store, tmp_path)

    assert len(result.weeks) == 4
    assert result.is_rising, [f"{w.label}: {w.autonomy_rate:.0%}" for w in result.weeks]
    assert result.first_rate < 0.5, "week 1 should mostly need the user"
    assert result.last_rate > 0.8, "week 4 should mostly not"


def test_the_interrupt_rate_falls(store, tmp_path):
    """The product's actual claim: the agent earns the right to stop asking."""
    result = run_replay(store, tmp_path)

    assert result.weeks[-1].decisions_raised < result.weeks[0].decisions_raised


def test_week_four_still_asks_about_something_genuinely_new(store, tmp_path):
    """It must not reach 100%.

    An agent that stopped asking entirely would have stopped being trustworthy,
    and a demo that shows a flat 100% invites exactly the question we do not want
    — 'so what happens when something new turns up?'. A brand-new merchant in the
    final week is the answer, on screen.
    """
    result = run_replay(store, tmp_path)

    assert result.weeks[-1].decisions_raised >= 1
    assert result.last_rate < 1.0


def test_the_curve_is_flat_when_the_user_never_teaches_a_rule(store, tmp_path):
    """**The load-bearing test in this file.**

    Same weeks, same actions, same code — answered with `APPROVE`, which approves
    without creating a policy. If the curve came from `replay.py`'s data it would
    climb regardless. It does not, because `policy.py` computes it:

        approve_always   4 -> 2 -> 1 -> 1 decisions   (43% -> 86%)
        approve          4 -> 4 -> 3 -> 3 decisions   (43% -> 57%)

    The untaught line is not perfectly flat, and that is expected rather than
    awkward: weeks 3 and 4 happen to contain a larger share of routine work, so
    the ratio drifts up a little on its own. What never happens without teaching
    is a rule being applied — which is why `policies_applied` is asserted at zero
    rather than the rate being asserted constant.
    """
    taught = run_replay(store, tmp_path)

    untaught_store = JsonStore(tmp_path / "store2")
    untaught = replay(
        HOUSEHOLD,
        store=untaught_store,
        session_dir=tmp_path / "sessions2",
        weeks=WEEKS,
        answer=DecisionChoice.APPROVE,
        start=datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert not untaught_store.list_policies(HOUSEHOLD), "APPROVE must not teach a rule"
    assert all(week.policies_applied == 0 for week in untaught.weeks)

    # The metric the product actually claims to move.
    assert untaught.weeks[-1].decisions_raised >= untaught.weeks[0].decisions_raised - 1
    assert taught.weeks[-1].decisions_raised < untaught.weeks[-1].decisions_raised

    taught_lift = taught.last_rate - taught.first_rate
    untaught_lift = untaught.last_rate - untaught.first_rate
    assert taught_lift > untaught_lift * 2, (taught_lift, untaught_lift)


def test_every_rule_came_from_an_answer_the_user_gave(store, tmp_path):
    """No policy may appear that no decision produced. Autonomy is never granted
    invisibly — that is the promise the policies page makes."""
    run_replay(store, tmp_path)

    policies = store.list_policies(HOUSEHOLD)
    assert policies
    for policy in policies:
        assert policy.created_from_decision_id, policy.description
        assert store.get_decision(policy.created_from_decision_id) is not None


def test_no_rule_is_ever_created_for_a_never_auto_action(store, tmp_path):
    """`dispute_charge` and `close_account` are `NEVER_AUTO`. Even a household
    that answers 'always' to everything for four weeks cannot buy them autonomy."""
    run_replay(store, tmp_path)

    never_auto = {ActionKind.DISPUTE_CHARGE, ActionKind.CLOSE_ACCOUNT}
    for policy in store.list_policies(HOUSEHOLD):
        assert policy.action_kind not in never_auto, policy.description


def test_policies_accumulate_rather_than_reset_between_weeks(store, tmp_path):
    """The accumulation *is* the mechanism."""
    result = run_replay(store, tmp_path)

    counts = [week.policies_in_force for week in result.weeks]
    assert all(b >= a for a, b in pairwise(counts))
    assert counts[-1] > counts[0]


# --------------------------------------------------------------------------
# The bug that produced a fake 100% week
# --------------------------------------------------------------------------


def test_every_scenario_action_is_routed_to_a_node_that_owns_it():
    """`NODE_TOOLS` must agree with what each specialist was actually given.

    A mismatch is silent: the agent calls a tool it does not have, or the node
    never wakes, and the action simply does not happen. The week then looks
    quieter than it is — which is a lie in the one number the whole demo rests on.
    """
    from quiet_hours_agent.tools import BILL_TOOLS, NEGOTIATION_TOOLS, SCHEDULING_TOOLS

    owned = {
        "bill_analyst": {t.tool_name for t in BILL_TOOLS},
        "negotiator": {t.tool_name for t in NEGOTIATION_TOOLS},
        "scheduler": {t.tool_name for t in SCHEDULING_TOOLS},
    }

    for tool_name, node in NODE_TOOLS.items():
        assert tool_name in owned[node], f"{node} does not have {tool_name}"


def test_every_scenario_action_has_a_finding_that_wakes_its_node():
    """The other half of the same trap.

    Routing is by *finding kind*. An action assigned to the negotiator is never
    attempted unless some finding in that week wakes the negotiator. This is
    exactly how week 4's PhotoCloud cancellation silently vanished and the week
    reported a fraudulent 100%.
    """
    from quiet_hours_agent.graph import ROUTING

    for scenario in WEEKS:
        woken = {
            node
            for node, kinds in ROUTING.items()
            for item in scenario.items
            if item.finding_kind in kinds
        }
        needed = {act.node for item in scenario.items for act in item.actions}

        assert needed <= woken | {"bill_analyst"} or needed <= woken, (
            f"{scenario.label}: actions need {sorted(needed)} but only "
            f"{sorted(woken)} are woken by its findings"
        )


def test_the_measured_action_count_matches_the_scenario_data(store, tmp_path):
    """Every action a week describes actually ran, and none ran twice.

    This is the assertion that would have caught both bugs at once: week 4
    reported six actions for seven described (one never woke), and week 1
    reported ten for seven (interrupted ones counted twice).
    """
    result = run_replay(store, tmp_path)

    for week, scenario in zip(result.weeks, WEEKS, strict=True):
        assert week.actions_proposed == ScenarioStats.of(scenario).actions, scenario.label


def test_an_interrupted_action_is_counted_once(store, tmp_path):
    """The gate runs twice for anything that interrupts — once to raise it, once
    on resume to collect the answer. Counting both deflates the autonomy rate,
    because the denominator grows for exactly the actions the metric penalises."""
    result = run_replay(store, tmp_path, weeks=WEEKS[:1])
    week = result.weeks[0]

    assert week.actions_autonomous + week.decisions_raised == week.actions_proposed
    assert week.decisions_raised > 0, "week 1 must interrupt, or this proves nothing"


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def test_the_rendered_curve_is_ascii_only(store, tmp_path):
    """A cp1252 Windows console crashes on a block-drawing character, and losing
    the demo to a box glyph is an avoidable way to lose a hackathon."""
    text = render(run_replay(store, tmp_path), store=store, household_id=HOUSEHOLD)

    assert text.isascii(), [c for c in text if not c.isascii()]


def test_the_output_says_whose_data_this_is(store, tmp_path):
    """The mechanic and the arithmetic are real; the household is invented. A
    judge should not have to ask."""
    text = render(run_replay(store, tmp_path), store=store, household_id=HOUSEHOLD)

    assert "counted from the audit trail" in text
    assert "stand-in" in text


def test_a_week_with_nothing_to_do_reads_as_fully_autonomous():
    """Zero actions is the product working, not a missing measurement."""
    assert WeekResult(label="quiet", scenario_key="k").autonomy_rate == 1.0


def test_an_empty_replay_is_not_reported_as_rising():
    assert not ReplayResult().is_rising


# --------------------------------------------------------------------------
# The risk floor still holds under replay
# --------------------------------------------------------------------------


def test_no_scenario_can_lower_an_actions_risk_below_its_floor(store, tmp_path):
    """Scenarios state a proposed risk. `effective_risk` takes the max of that and
    the floor, so a scenario claiming `pay_bill` is silent still interrupts."""
    from quiet_hours_contracts import DEFAULT_RISK_BY_ACTION, RISK_ORDER

    run_replay(store, tmp_path)

    for entry in store.list_activity(HOUSEHOLD):
        action = store.get_action(entry.action_id)
        if action is None:
            continue
        floor = DEFAULT_RISK_BY_ACTION[action.kind]
        assert RISK_ORDER[entry.risk] >= RISK_ORDER[floor], entry.summary


def test_money_actions_never_ran_silently_before_a_rule_existed(store, tmp_path):
    """Week 1 has no policies at all, so nothing that spends money may be silent."""
    result = run_replay(store, tmp_path, weeks=WEEKS[:1])

    spending = [
        entry
        for entry in store.list_activity(HOUSEHOLD)
        if entry.risk in (RiskTier.CONFIRM, RiskTier.NEVER_AUTO)
    ]
    assert spending, "week 1 must contain spending actions, or this proves nothing"
    assert all(not entry.was_autonomous for entry in spending)
    assert result.weeks[0].policies_applied == 0
