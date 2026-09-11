"""The A5 graph: routing, gate coverage, and turning drafts into contracts.

The cross-process interrupt behaviour is covered by `test_a5_graph_spike.py`.
This file covers the wiring around it — the parts that are cheap to get subtly
wrong and expensive to notice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from quiet_hours_contracts import (
    DEFAULT_RISK_BY_ACTION,
    ActionKind,
    FindingKind,
    RiskTier,
)
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent
from strands.multiagent import Status

from quiet_hours_agent import graph as graph_module
from quiet_hours_agent.graph import (
    NODE_BILL_ANALYST,
    NODE_BRIEF,
    NODE_NEGOTIATOR,
    NODE_SCHEDULER,
    NODE_TRIAGE,
    ROUTING,
    SPECIALISTS,
    annual_savings_from,
    build_graph,
    harvest,
)
from quiet_hours_agent.prompts import PromptNotFoundError, load_prompt
from quiet_hours_agent.schemas import (
    ActionPlan,
    DraftAction,
    DraftEvidence,
    DraftFinding,
    action_from_draft,
    finding_from_draft,
)
from quiet_hours_agent.store import JsonStore, new_id
from quiet_hours_agent.tools import ACTION_TOOLS

HOUSEHOLD = "hh_graph_test"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("QH_PROVIDER_MODE", "mock")
    monkeypatch.setenv("QH_STORE_DIR", str(tmp_path / "store"))
    return JsonStore(tmp_path / "store")


@pytest.fixture
def run(store, tmp_path):
    return build_graph(
        HOUSEHOLD,
        store=store,
        run_id=new_id("run"),
        session_id="qh-graph-test",
        session_dir=tmp_path / "sessions",
        mode="mock",
    )


# -- the safety property this whole file exists to protect ------------------


def test_every_specialist_carries_the_policy_gate(run):
    """A specialist without `PolicyHook` is an ungoverned path to a bank account.

    Graph-level hook providers never see `BeforeToolCallEvent` — the tool
    executor dispatches it through the agent's own registry — so the gate has to
    be on each node agent. Nothing in the SDK enforces that, which is exactly why
    it is enforced here.
    """
    for node_id in SPECIALISTS:
        registry = run.graph.nodes[node_id].executor.hooks
        callbacks = registry._registered_callbacks
        assert BeforeToolCallEvent in callbacks, f"{node_id} has no policy gate"
        assert AfterToolCallEvent in callbacks, f"{node_id} writes no audit trail"


def test_every_node_that_holds_an_action_tool_is_gated(run):
    """The rule generalised: holding a governed tool implies holding the gate."""
    governed = {tool.tool_name for tool in ACTION_TOOLS}

    for node_id, node in run.graph.nodes.items():
        tool_names = set(getattr(node.executor, "tool_names", []) or [])
        if not tool_names & governed:
            continue
        callbacks = node.executor.hooks._registered_callbacks
        assert BeforeToolCallEvent in callbacks, (
            f"{node_id} holds governed tools {sorted(tool_names & governed)} but has no gate"
        )


def test_every_governed_tool_is_named_after_its_action_kind():
    """Naming *is* the registration mechanism — see `tools/__init__.py`."""
    kinds = {kind.value for kind in ActionKind}
    for tool in ACTION_TOOLS:
        assert tool.tool_name in kinds, f"{tool.tool_name} would pass through ungoverned"


def test_no_tool_exists_for_the_two_kinds_we_deliberately_refuse():
    """`send_email` and `close_account` have no tool at all, by design.

    Not having the tool is a stronger guarantee than gating it. If one appears,
    that is a safety decision and belongs in `DECISIONS.md` first.
    """
    names = {tool.tool_name for tool in ACTION_TOOLS}
    assert ActionKind.SEND_EMAIL.value not in names
    assert ActionKind.CLOSE_ACCOUNT.value not in names


# -- routing ----------------------------------------------------------------


def _state_with(*kinds: FindingKind) -> SimpleNamespace:
    """A stand-in for `GraphState` carrying just what the conditions read.

    Built by hand rather than by running triage: the point is to exercise the
    routing table against finding kinds the mock script never produces.
    """
    agent_result = SimpleNamespace(
        structured_output=SimpleNamespace(
            findings=[SimpleNamespace(kind=kind) for kind in kinds]
        )
    )
    node_result = SimpleNamespace(get_agent_results=lambda: [agent_result])
    return SimpleNamespace(results={NODE_TRIAGE: node_result})


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (FindingKind.BILL_DUE, {NODE_BILL_ANALYST}),
        (FindingKind.PRICE_INCREASE, {NODE_BILL_ANALYST}),
        (FindingKind.UNUSED_SUBSCRIPTION, {NODE_NEGOTIATOR}),
        (FindingKind.TRIAL_CONVERTING, {NODE_NEGOTIATOR}),
        (FindingKind.APPOINTMENT_NEEDS_REPLY, {NODE_SCHEDULER}),
        # A renewal is both something to push back on and something to diarise.
        (FindingKind.RENEWAL_UPCOMING, {NODE_NEGOTIATOR, NODE_SCHEDULER}),
    ],
)
def test_a_finding_wakes_exactly_the_specialists_that_can_act_on_it(kind, expected):
    state = _state_with(kind)
    woken = {node_id for node_id in SPECIALISTS if graph_module._wakes(node_id, state)}
    assert woken == expected


def test_nothing_to_do_wakes_nobody_but_still_produces_a_brief():
    """The common case: a quiet day still owes the user a digest.

    Without the `triage -> brief` shortcut the graph would simply stop after
    triage and the user would hear nothing at all, which reads as the agent being
    broken rather than the day being quiet.
    """
    state = _state_with(FindingKind.NOTHING_TO_DO)
    assert not any(graph_module._wakes(node_id, state) for node_id in SPECIALISTS)
    assert graph_module._quiet_day_route(state) is True


def test_routing_conditions_survive_a_node_that_produced_nothing():
    """An edge condition that raises fails the whole run, so none may raise."""

    empty = SimpleNamespace(results={})

    for condition in (
        graph_module._bill_route,
        graph_module._negotiator_route,
        graph_module._scheduler_route,
    ):
        assert condition(empty) is False
    assert graph_module._quiet_day_route(empty) is True


def test_every_specialist_has_a_routing_entry():
    assert set(ROUTING) == set(SPECIALISTS)


# -- prompts ----------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["ingest", NODE_TRIAGE, NODE_BILL_ANALYST, NODE_NEGOTIATOR, NODE_SCHEDULER, NODE_BRIEF]
)
def test_every_node_has_a_prompt_file(name):
    """Prompts are `.md` files, never inline strings (`agent/AGENTS.md` rule 4)."""
    assert load_prompt(name).strip()


def test_a_missing_prompt_fails_loudly_rather_than_silently_empty():
    with pytest.raises(PromptNotFoundError):
        load_prompt("no_such_node")


# -- drafts become contract objects, with identity owned by us --------------


def test_a_draft_finding_never_supplies_its_own_identity():
    """`household_id` is a tenancy boundary and is not the model's to set."""
    assert "household_id" not in DraftFinding.model_fields
    assert "run_id" not in DraftFinding.model_fields
    assert "finding_id" not in DraftFinding.model_fields

    draft = DraftFinding(
        kind=FindingKind.BILL_DUE,
        title="Gas bill due",
        detail="It is due on the 28th.",
        confidence=0.9,
        amount_minor=8420,
        evidence=[DraftEvidence(signal_id="sig_1", excerpt="due on the 28th")],
    )
    now = datetime.now(UTC)
    finding = finding_from_draft(
        draft, finding_id="fin_1", household_id=HOUSEHOLD, run_id="run_1", created_at=now
    )

    assert finding.household_id == HOUSEHOLD
    assert finding.run_id == "run_1"
    assert finding.amount.amount_minor == 8420
    assert finding.amount.currency == "GBP"


def test_a_draft_action_keeps_the_risk_the_model_asked_for():
    """`action_from_draft` must not clamp risk — `effective_risk` owns the floor.

    Clamping here would put the safety rule in two places, and the one in
    `policy.py` is the one with the test named after it.
    """
    draft = DraftAction(
        kind=ActionKind.FILE_RECORD,
        summary="File a record",
        rationale="Because.",
        risk=RiskTier.NEVER_AUTO,
        evidence=[DraftEvidence(signal_id="sig_1", excerpt="x")],
    )
    action = action_from_draft(
        draft,
        action_id="act_1",
        household_id=HOUSEHOLD,
        run_id="run_1",
        created_at=datetime.now(UTC),
    )
    # Raised, not lowered — the model may always be more careful than the floor.
    assert action.risk is RiskTier.NEVER_AUTO
    assert DEFAULT_RISK_BY_ACTION[ActionKind.FILE_RECORD] is RiskTier.SILENT


def test_an_action_plan_may_legitimately_be_empty():
    """Proposing nothing is a good outcome, not a failure to parse."""
    assert ActionPlan().actions == []


# -- the whole graph, in mock mode ------------------------------------------


def test_a_full_mock_run_routes_reasons_and_stops_once(run, store):
    """End to end: the shape of the demo, asserted rather than eyeballed."""
    result = run("Do this household's admin for today.")

    assert result.status is Status.INTERRUPTED
    assert len(result.interrupts) == 1, "exactly one thing should need the user"

    ran = set(result.results)
    assert {"ingest", NODE_TRIAGE} <= ran

    # All three specialists were woken, but only two *completed*: the negotiator
    # is suspended mid tool call, so it has no result yet. That asymmetry is the
    # interrupt mechanic visible in the graph's own bookkeeping.
    assert {NODE_BILL_ANALYST, NODE_SCHEDULER} <= ran
    assert NODE_NEGOTIATOR not in ran, "the interrupted node must not report a result"
    assert result.interrupted_nodes == 1

    assert NODE_BRIEF not in ran, "the brief must wait until the user has answered"

    # The one thing that stopped is the one that spends money.
    assert result.interrupts[0].reason["headline"].startswith("Cancel subscription")

    outcome = harvest(result, run)
    assert [finding.kind for finding in outcome.findings] == [
        FindingKind.BILL_DUE,
        FindingKind.UNUSED_SUBSCRIPTION,
        FindingKind.TRIAL_CONVERTING,
        FindingKind.APPOINTMENT_NEEDS_REPLY,
    ]
    assert all(finding.household_id == HOUSEHOLD for finding in outcome.findings)
    assert all(finding.evidence for finding in outcome.findings)

    # Two silent actions completed before the interrupt; the third asked.
    verdicts = run.policy_hook.verdicts
    assert sum(1 for _, verdict in verdicts if verdict.allow_silently) == 2
    assert sum(1 for _, verdict in verdicts if not verdict.allow_silently) == 1


def test_the_brief_measures_its_numbers_rather_than_quoting_the_model(run):
    """`autonomy_rate` is counted from the audit trail, never written by a model.

    A brief is the one artefact the user reads as fact. A figure the model
    estimated would be indistinguishable from one that was counted.
    """
    result = run("Do this household's admin for today.")
    outcome = harvest(result, run, pending_decision_ids=["dec_x"])

    assert outcome.brief is not None
    verdicts = run.policy_hook.verdicts
    expected = sum(1 for _, v in verdicts if v.allow_silently) / len(verdicts)
    assert outcome.brief.autonomy_rate == pytest.approx(expected)
    assert outcome.brief.pending_decision_ids == ["dec_x"]
    assert outcome.brief.household_id == HOUSEHOLD


def test_the_model_never_sets_the_household_on_anything_it_produces(run, store):
    """Tenancy comes from `invocation_state`, which the model cannot reach."""
    assert run.invocation_state["household_id"] == HOUSEHOLD

    result = run("Do this household's admin for today.")
    outcome = harvest(result, run)

    for record in [*outcome.findings, *outcome.actions]:
        assert record.household_id == HOUSEHOLD
        assert record.run_id == run.run_id


# --------------------------------------------------------------------------
# Findings get their identity before the specialists act on them
# --------------------------------------------------------------------------


def test_findings_exist_before_the_specialists_run(run, store):
    """`FindingRecorder` promotes triage's drafts on `AfterNodeCallEvent`, which
    is the only seam between triage finishing and a specialist starting. Before
    it existed, findings were minted in `harvest()` after the whole graph — so
    every tool call the specialists made was backed by nothing."""
    run("Do this household's admin for today.")

    findings = run.invocation_state.get("findings")
    assert findings, "triage's findings must reach invocation_state"
    assert all(f.finding_id.startswith("fin_") for f in findings)
    assert all(f.run_id == run.run_id for f in findings)

    for action, _verdict in run.policy_hook.verdicts:
        assert action.finding_id != "unbacked", action.summary
        assert action.evidence[0].signal_id != "unbacked", action.summary


def test_harvest_reuses_the_recorded_findings_rather_than_minting_new_ids(run, store):
    """Two sets of ids for one set of findings would mean the id on the card and
    the id in the store disagree — the exact bug the recorder closes."""
    result = run("Do this household's admin for today.")
    recorded = [f.finding_id for f in run.invocation_state["findings"]]

    outcome = harvest(result, run)

    assert [f.finding_id for f in outcome.findings] == recorded


def test_every_action_cites_a_finding_that_exists(run, store):
    """The join Lane B renders: card -> action -> finding -> evidence."""
    result = run("Do this household's admin for today.")
    outcome = harvest(result, run)
    known = {f.finding_id for f in outcome.findings}

    for action, _verdict in run.policy_hook.verdicts:
        assert action.finding_id in known


# --------------------------------------------------------------------------
# The savings figure
# --------------------------------------------------------------------------


def _action(kind: ActionKind, amount_minor: int | None, *, currency: str = "GBP"):
    from quiet_hours_contracts import Evidence, Money, ProposedAction

    return ProposedAction(
        action_id=f"act_{kind.value}",
        household_id=HOUSEHOLD,
        run_id="run_x",
        finding_id="fin_x",
        kind=kind,
        risk=DEFAULT_RISK_BY_ACTION[kind],
        summary=kind.value,
        rationale="because",
        reversible=True,
        evidence=[Evidence(signal_id="sig_x", excerpt="the line it came from")],
        estimated_impact=(
            None if amount_minor is None else Money(amount_minor=amount_minor, currency=currency)
        ),
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
    )


def test_a_cancelled_subscription_is_worth_twelve_months():
    """GBP 38 a month that stops recurring is GBP 456 a year."""
    savings = annual_savings_from([_action(ActionKind.CANCEL_SUBSCRIPTION, 3800)])

    assert savings is not None
    assert savings.amount_minor == 45600


def test_a_one_off_refund_is_not_annualised():
    """Winning a GBP 38 dispute saves GBP 38. Multiplying it by twelve is the
    kind of arithmetic that makes a demo unbelievable to anyone who checks."""
    savings = annual_savings_from([_action(ActionKind.DISPUTE_CHARGE, 3800)])

    assert savings is not None
    assert savings.amount_minor == 3800


def test_paying_a_bill_is_not_a_saving():
    """`pay_bill` carries the largest `estimated_impact` in the whole trail and
    is money going out, not money kept."""
    assert annual_savings_from([_action(ActionKind.PAY_BILL, 8420)]) is None


def test_nothing_saved_is_none_rather_than_zero():
    """`Money(0)` on the chart reads as a measured zero. The field is optional
    precisely so 'nothing to report' is distinguishable from 'we counted, it was
    nought'."""
    assert annual_savings_from([]) is None
    assert annual_savings_from([_action(ActionKind.FILE_RECORD, 1000)]) is None


def test_an_action_with_no_impact_is_skipped():
    assert annual_savings_from([_action(ActionKind.CANCEL_SUBSCRIPTION, None)]) is None


def test_mixed_currencies_are_not_summed(caplog):
    """A single household is realistically one currency, and a silently wrong
    total is worse than a slightly incomplete one."""
    with caplog.at_level("WARNING"):
        savings = annual_savings_from(
            [
                _action(ActionKind.CANCEL_SUBSCRIPTION, 1000),
                _action(ActionKind.DOWNGRADE_PLAN, 1000, currency="USD"),
            ]
        )

    assert savings is not None
    assert savings.currency == "GBP"
    assert savings.amount_minor == 12000
    assert any("does not match" in record.message for record in caplog.records)


def test_an_interrupted_action_is_not_counted_as_executed(run, store):
    """It is a proposal until the user answers, and may never happen at all.
    Counting it would let the savings figure be inflated by asking for things
    rather than by doing them."""
    run("Do this household's admin for today.")

    executed = {action.action_id for action in run.policy_hook.executed}
    interrupted = [
        action for action, verdict in run.policy_hook.verdicts if not verdict.allow_silently
    ]

    assert interrupted, "the demo day must still interrupt at least once"
    for action in interrupted:
        assert action.action_id not in executed, action.summary


def test_everything_executed_passed_through_the_gate(run, store):
    """`executed` is recorded in `audit()`, which only ever fires for a call the
    gate produced a verdict for. Nothing can reach the savings figure without
    having been governed."""
    run("Do this household's admin for today.")

    governed = {action.action_id for action, _verdict in run.policy_hook.verdicts}

    assert run.policy_hook.executed
    for action in run.policy_hook.executed:
        assert action.action_id in governed
