"""A3 — the policy engine wired into the real `PolicyHook`.

These run the gate through an actual `strands.Agent`, not a mocked event, because
the thing worth testing is the interaction: does a real tool call actually get
stopped, and does a real resume actually let it through?

Cross-process durability is covered separately in `test_a1_interrupt_spike.py`.
These are in-process for speed — the two files together cover the mechanic.

The scripted model is reused from the A1 spike rather than duplicated; it is the
one already proven to drive this loop deterministically without credentials.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from quiet_hours_contracts import (
    ActionKind,
    DecisionChoice,
    DecisionResponse,
    DecisionStatus,
    Evidence,
    Finding,
    FindingKind,
    Money,
    Policy,
    PolicyScope,
    RiskTier,
)
from strands import Agent, tool

from quiet_hours_agent.hooks import PolicyHook, decision_id_for
from quiet_hours_agent.resume import build_resume_payload, persist_decisions, was_interrupted
from quiet_hours_agent.store import JsonStore
from spikes.a1_interrupt.scripted_model import ScriptedModel

HOUSEHOLD = "hh_test"
RUN = "run_test"
SESSION = "sess_test"

executed: list[str] = []


@tool
def file_record(merchant: str) -> str:
    """File a record. Silent tier.

    Args:
        merchant: Who the record is about.
    """
    executed.append(f"file_record:{merchant}")
    return "filed"


@tool
def cancel_subscription(merchant: str, monthly_amount_minor: int) -> str:
    """Cancel a subscription. Confirm tier.

    Args:
        merchant: Service to cancel.
        monthly_amount_minor: Monthly charge in minor units.
    """
    executed.append(f"cancel_subscription:{merchant}")
    return f"cancelled {merchant}"


@tool
def dispute_charge(merchant: str, amount_minor: int) -> str:
    """Dispute a charge. Never-auto tier.

    Args:
        merchant: Who charged.
        amount_minor: Disputed amount in minor units.
    """
    executed.append(f"dispute_charge:{merchant}")
    return f"disputed {merchant}"


@tool
def read_inbox(query: str) -> str:
    """Read the inbox. Not an action kind, so ungoverned.

    Args:
        query: What to look for.
    """
    executed.append(f"read_inbox:{query}")
    return "3 messages"


ALL_TOOLS = [file_record, cancel_subscription, dispute_charge, read_inbox]


@pytest.fixture(autouse=True)
def _reset():
    executed.clear()
    yield
    executed.clear()


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / "store")


def build(store, tool_name: str, tool_input: dict, policies: list[Policy] | None = None):
    """An agent whose model deterministically calls `tool_name` once."""
    hook = PolicyHook(HOUSEHOLD, policies if policies is not None else [], store, run_id=RUN)
    agent = Agent(
        model=ScriptedModel(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=f"tooluse_{tool_name}",
            final_text="done",
        ),
        tools=ALL_TOOLS,
        hooks=[hook],
        callback_handler=None,
    )
    return agent, hook


def approve_policy(**overrides) -> Policy:
    base = {
        "policy_id": "pol_test",
        "household_id": HOUSEHOLD,
        "scope": PolicyScope.MERCHANT,
        "action_kind": ActionKind.CANCEL_SUBSCRIPTION,
        "merchant": "FitLife",
        "effect": "auto_approve",
        "description": "Always cancel FitLife",
        "created_at": datetime.now(UTC),
    }
    base.update(overrides)
    return Policy(**base)


# -- the silent path -------------------------------------------------------


def test_silent_action_executes_without_asking(store):
    agent, _hook = build(store, "file_record", {"merchant": "FitLife"})
    result = agent("file it")

    assert not was_interrupted(result)
    assert executed == ["file_record:FitLife"]

    entries = store.list_activity(HOUSEHOLD)
    assert len(entries) == 1
    assert entries[0].was_autonomous is True
    assert entries[0].succeeded is True
    assert entries[0].risk is RiskTier.SILENT


def test_ungoverned_tool_is_not_gated_at_all(store):
    agent, hook = build(store, "read_inbox", {"query": "bills"})
    result = agent("read it")

    assert not was_interrupted(result)
    assert executed == ["read_inbox:bills"]
    assert hook.verdicts == []
    assert store.list_activity(HOUSEHOLD) == []


# -- the interrupt path ----------------------------------------------------


def test_confirm_action_interrupts_and_does_not_execute(store):
    agent, _ = build(
        store, "cancel_subscription", {"merchant": "FitLife", "monthly_amount_minor": 3800}
    )
    result = agent("cancel it")

    assert was_interrupted(result)
    assert executed == []

    cards = persist_decisions(result, store, session_id=SESSION)
    assert len(cards) == 1
    card = cards[0]
    assert card.decision_id == decision_id_for("tooluse_cancel_subscription")
    assert card.session_id == SESSION
    assert card.interrupt_id == result.interrupts[0].id
    assert card.status is DecisionStatus.PENDING
    assert card.why_asking


def test_policy_lets_a_confirm_action_through_silently(store):
    agent, _ = build(
        store,
        "cancel_subscription",
        {"merchant": "FitLife", "monthly_amount_minor": 3800},
        policies=[approve_policy()],
    )
    result = agent("cancel it")

    assert not was_interrupted(result)
    assert executed == ["cancel_subscription:FitLife"]

    entry = store.list_activity(HOUSEHOLD)[0]
    assert entry.was_autonomous is True
    assert entry.policy_id == "pol_test"


def test_never_auto_cannot_be_policy_approved_through_the_hook(store):
    """The safety guarantee, exercised end to end rather than as a unit.

    `policy.py` has its own unit test for this. This one proves the wiring did
    not accidentally route around it.
    """
    blanket = approve_policy(
        policy_id="pol_blanket",
        scope=PolicyScope.GLOBAL,
        action_kind=None,
        merchant=None,
        description="Always do everything",
    )
    agent, _ = build(
        store,
        "dispute_charge",
        {"merchant": "FitLife", "amount_minor": 9900},
        policies=[blanket],
    )
    result = agent("dispute it")

    assert was_interrupted(result), "a NEVER_AUTO action was auto-approved by a policy"
    assert executed == []


def test_never_auto_card_does_not_offer_approve_always(store):
    """Offering the button would be a lie: the engine ignores such a policy."""
    agent, _ = build(store, "dispute_charge", {"merchant": "FitLife", "amount_minor": 9900})
    result = agent("dispute it")

    card = persist_decisions(result, store, session_id=SESSION)[0]
    choices = {option.choice for option in card.options}
    assert DecisionChoice.APPROVE_ALWAYS not in choices
    assert DecisionChoice.APPROVE in choices
    assert len(card.options) >= 2  # the contract's minimum


# -- resuming --------------------------------------------------------------


def respond(card, choice: DecisionChoice) -> DecisionResponse:
    return DecisionResponse(
        decision_id=card.decision_id, choice=choice, responded_at=datetime.now(UTC)
    )


def test_approving_resumes_the_run_and_executes_the_tool(store):
    agent, _ = build(
        store, "cancel_subscription", {"merchant": "FitLife", "monthly_amount_minor": 3800}
    )
    result = agent("cancel it")
    card = persist_decisions(result, store, session_id=SESSION)[0]

    assert executed == []

    final = agent(build_resume_payload([(card, respond(card, DecisionChoice.APPROVE))]))

    assert not was_interrupted(final)
    assert executed == ["cancel_subscription:FitLife"]

    assert store.get_decision(card.decision_id).status is DecisionStatus.RESOLVED
    entry = store.list_activity(HOUSEHOLD)[0]
    assert entry.was_autonomous is False
    assert entry.succeeded is True
    assert entry.decision_id == card.decision_id


def test_denying_cancels_the_tool_and_still_writes_an_audit_entry(store):
    agent, _ = build(
        store, "cancel_subscription", {"merchant": "FitLife", "monthly_amount_minor": 3800}
    )
    result = agent("cancel it")
    card = persist_decisions(result, store, session_id=SESSION)[0]

    final = agent(build_resume_payload([(card, respond(card, DecisionChoice.DENY))]))

    assert not was_interrupted(final)
    assert executed == []

    entry = store.list_activity(HOUSEHOLD)[0]
    assert entry.succeeded is False
    assert "declined" in (entry.error or "").casefold()


def test_approve_always_creates_a_policy(store):
    agent, hook = build(
        store, "cancel_subscription", {"merchant": "FitLife", "monthly_amount_minor": 3800}
    )
    result = agent("cancel it")
    card = persist_decisions(result, store, session_id=SESSION)[0]

    agent(build_resume_payload([(card, respond(card, DecisionChoice.APPROVE_ALWAYS))]))

    assert executed == ["cancel_subscription:FitLife"]
    assert len(hook.new_policies) == 1

    saved = store.list_policies(HOUSEHOLD)
    assert len(saved) == 1
    assert saved[0].effect == "auto_approve"
    assert saved[0].created_from_decision_id == card.decision_id
    assert saved[0].description  # shown verbatim to the user


def test_approve_always_never_creates_a_policy_for_never_auto(store):
    agent, hook = build(store, "dispute_charge", {"merchant": "FitLife", "amount_minor": 9900})
    result = agent("dispute it")
    card = persist_decisions(result, store, session_id=SESSION)[0]

    agent(build_resume_payload([(card, respond(card, DecisionChoice.APPROVE_ALWAYS))]))

    assert hook.new_policies == []
    assert store.list_policies(HOUSEHOLD) == []


# -- fail-closed answer handling -------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [None, "", "maybe", 42, ["approve"], {"choice": "nonsense"}, {"not_a_choice": 1}],
)
def test_unreadable_answers_are_treated_as_denials(store, answer):
    hook = PolicyHook(HOUSEHOLD, [], store, run_id=RUN)
    parsed = hook._parse_response(answer, "dec_x")
    assert parsed is None or parsed.choice not in (
        DecisionChoice.APPROVE,
        DecisionChoice.APPROVE_ALWAYS,
    )


def test_snooze_does_not_execute_the_tool(store):
    agent, _ = build(
        store, "cancel_subscription", {"merchant": "FitLife", "monthly_amount_minor": 3800}
    )
    result = agent("cancel it")
    card = persist_decisions(result, store, session_id=SESSION)[0]

    agent(build_resume_payload([(card, respond(card, DecisionChoice.SNOOZE))]))

    assert executed == []
    entry = store.list_activity(HOUSEHOLD)[0]
    assert entry.succeeded is False
    assert "snooze" in (entry.error or "").casefold()


# -- improvised tool calls -------------------------------------------------


def test_an_improvised_tool_call_is_still_gated(store):
    """The model inventing a call it has no finding for must not bypass the gate."""
    agent, hook = build(
        store, "cancel_subscription", {"merchant": "Ghost", "monthly_amount_minor": 100}
    )
    result = agent("cancel something")

    assert was_interrupted(result)
    action, verdict = hook.verdicts[0]
    assert action.finding_id == "unbacked"
    assert verdict.allow_silently is False


def test_a_stored_action_is_used_when_the_tool_cites_one(store):
    from quiet_hours_contracts import Evidence, ProposedAction

    action = ProposedAction(
        action_id="act_known",
        household_id=HOUSEHOLD,
        run_id=RUN,
        finding_id="find_1",
        kind=ActionKind.CANCEL_SUBSCRIPTION,
        risk=RiskTier.CONFIRM,
        summary="Cancel FitLife (£38/mo)",
        rationale="Unused for 90 days.",
        params={"merchant": "FitLife"},
        estimated_impact=Money(amount_minor=45600, currency="GBP"),
        evidence=[Evidence(signal_id="sig_1", excerpt="No visits since May.")],
        created_at=datetime.now(UTC),
    )
    store.put_action(action)

    agent, hook = build(
        store,
        "cancel_subscription",
        {"merchant": "FitLife", "monthly_amount_minor": 3800, "action_id": "act_known"},
    )
    result = agent("cancel it")

    card = persist_decisions(result, store, session_id=SESSION)[0]
    assert card.action_id == "act_known"
    assert card.headline == "Cancel FitLife (£38/mo)"
    assert card.body == "Unused for 90 days."
    assert hook.verdicts[0][0].finding_id == "find_1"


def test_an_interrupted_action_is_counted_once_across_the_resume(store):
    """The gate runs twice for anything that interrupts — once to raise it, once
    on resume to collect the answer (A1). `verdicts` is keyed by `toolUseId`, so
    the second pass replaces the first rather than adding to it.

    Counting both deflated the autonomy rate: the denominator grew by one for
    every action the user was asked about, which is exactly what the metric is
    supposed to penalise. It was wrong in the pessimistic direction, which is why
    it went unnoticed until the A6 replay compared the count against the scenario
    data that produced it.
    """
    agent, hook = build(
        store, "cancel_subscription", {"merchant": "FitLife", "monthly_amount_minor": 3800}
    )

    result = agent("cancel it")
    card = persist_decisions(result, store, session_id=SESSION)[0]
    assert len(hook.verdicts) == 1, "one tool call, one verdict"

    agent(build_resume_payload([(card, respond(card, DecisionChoice.APPROVE))]))

    assert len(hook.verdicts) == 1, "the resume re-gates the same call, it is not a second one"
    _action, verdict = hook.verdicts[0]
    assert verdict.allow_silently is False


def test_two_distinct_tool_calls_are_counted_separately(store):
    """The other side of the dedup: keying by `toolUseId` must not collapse two
    genuinely different actions into one. This is the failure mode A5 already hit
    once, when parallel nodes shared a tool use id and one node's audit entry
    overwrote another's."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})

    from quiet_hours_agent.policy import evaluate

    action = hook._action_from_tool_use(
        {"toolUseId": "tooluse_a", "name": "file_record", "input": {"merchant": "A"}},
        {"household_id": HOUSEHOLD, "run_id": RUN},
    )
    hook._verdicts["tooluse_a"] = (action, evaluate(action, []))
    hook._verdicts["tooluse_b"] = (action, evaluate(action, []))

    assert len(hook.verdicts) == 2


# --------------------------------------------------------------------------
# Backing a card with the finding it came from
# --------------------------------------------------------------------------
#
# Every decision card the product had ever raised cited `signal_id="unbacked"`
# and an excerpt reading "Tool call cancel_subscription with ['merchant', ...]".
# That string was what the user read under "why am I being asked this".
#
# The cause was ordering: findings got their ids in `graph.harvest()`, which runs
# after the whole graph, so while a specialist was calling the tool there was no
# finding to point at. `graph.FindingRecorder` now promotes them between triage
# and the specialists, and the gate matches the call to one.


def _finding(finding_id: str, *, merchant: str, signal_id: str, **kwargs) -> Finding:
    return Finding(
        finding_id=finding_id,
        household_id=HOUSEHOLD,
        run_id=RUN,
        kind=kwargs.pop("kind", FindingKind.UNUSED_SUBSCRIPTION),
        title=kwargs.pop("title", f"{merchant} needs a look"),
        detail="detail",
        confidence=kwargs.pop("confidence", 0.9),
        merchant=merchant,
        category=kwargs.pop("category", "fitness"),
        evidence=[Evidence(signal_id=signal_id, excerpt=f"the line from {merchant}")],
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
    )


def _state(*findings: Finding) -> dict:
    return {"household_id": HOUSEHOLD, "run_id": RUN, "findings": list(findings)}


def _call(hook: PolicyHook, name: str, tool_input: dict, state: dict):
    return hook._action_from_tool_use(
        {"toolUseId": "tooluse_x", "name": name, "input": tool_input}, state
    )


def test_a_card_cites_the_evidence_its_finding_was_built_on(store):
    """The regression test for the `unbacked` bug."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})
    finding = _finding("fin_1", merchant="FitLife", signal_id="sig_fitlife_charge")

    action = _call(hook, "cancel_subscription", {"merchant": "FitLife"}, _state(finding))

    assert action.finding_id == "fin_1"
    assert [e.signal_id for e in action.evidence] == ["sig_fitlife_charge"]
    assert action.evidence[0].excerpt == "the line from FitLife"


def test_the_findings_category_reaches_the_action(store):
    """`_category_of` reads `params["category"]`, and it is what a `CATEGORY`
    scoped policy is learned and matched against. Only `tag_merchant` takes a
    category argument, so without this the scope was nearly unreachable."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})
    finding = _finding("fin_1", merchant="FitLife", signal_id="sig_x", category="fitness")

    action = _call(hook, "cancel_subscription", {"merchant": "FitLife"}, _state(finding))

    assert action.params["category"] == "fitness"


def test_a_category_on_the_call_is_not_overwritten(store):
    """`tag_merchant` states one explicitly, and the call is more specific than
    the finding it came from."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})
    finding = _finding("fin_1", merchant="FitLife", signal_id="sig_x", category="fitness")

    action = _call(
        hook, "tag_merchant", {"merchant": "FitLife", "category": "wellbeing"}, _state(finding)
    )

    assert action.params["category"] == "wellbeing"


def test_a_merchant_named_only_in_free_text_still_resolves(store):
    """The scheduling tools take no `merchant` — a reminder has a subject, a
    calendar entry a title — but they name the merchant inside it. Without this
    every scheduler action would be unbacked."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})
    finding = _finding("fin_dentist", merchant="Bridge Street Dental", signal_id="sig_dentist_appt")

    action = _call(
        hook,
        "set_reminder",
        {"subject": "Confirm dental check-up with Bridge Street Dental"},
        _state(finding),
    )

    assert action.finding_id == "fin_dentist"


def test_an_explicit_finding_id_wins_over_the_merchant(store):
    """No tool declares `finding_id` yet, so nothing can supply one. The branch
    is where a citation would be honoured once the id exists to be cited."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})
    cited = _finding("fin_cited", merchant="Streamly", signal_id="sig_streamly")
    by_merchant = _finding("fin_merchant", merchant="FitLife", signal_id="sig_fitlife")

    action = _call(
        hook,
        "cancel_subscription",
        {"merchant": "FitLife", "finding_id": "fin_cited"},
        _state(cited, by_merchant),
    )

    assert action.finding_id == "fin_cited"


def test_an_unmatched_call_stays_honestly_unbacked(store):
    """An improvised tool call is legitimate and still passes the gate at its
    floor risk. What it must not do is claim evidence it does not have — a card
    citing a signal that does not exist is worse than one citing none."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})
    finding = _finding("fin_1", merchant="FitLife", signal_id="sig_fitlife")

    action = _call(hook, "cancel_subscription", {"merchant": "Acme"}, _state(finding))

    assert action.finding_id == "unbacked"
    assert action.evidence[0].signal_id == "unbacked"
    assert action.risk is RiskTier.CONFIRM, "still gated at the floor for its kind"


def test_two_findings_for_one_merchant_take_the_most_confident(store, caplog):
    """A bill and a price rise from the same merchant in one run. Confidence is
    the only ordering triage gives us, and picking silently would hide a real
    ambiguity from whoever reads the trail."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})
    low = _finding("fin_low", merchant="FitLife", signal_id="sig_a", confidence=0.4)
    high = _finding("fin_high", merchant="FitLife", signal_id="sig_b", confidence=0.95)

    with caplog.at_level("WARNING"):
        action = _call(hook, "file_record", {"merchant": "FitLife"}, _state(low, high))

    assert action.finding_id == "fin_high"
    assert any("findings match this call" in record.message for record in caplog.records)


def test_a_run_with_no_findings_is_not_an_error(store):
    """`invocation_state` carries no findings when the graph was assembled by
    hand — every direct `PolicyHook` test in this file, for one."""
    _agent, hook = build(store, "file_record", {"merchant": "FitLife"})

    action = _call(
        hook, "file_record", {"merchant": "FitLife"}, {"household_id": HOUSEHOLD, "run_id": RUN}
    )

    assert action.finding_id == "unbacked"


def test_an_approved_action_counts_as_executed(store):
    """`RunStats.estimated_annual_savings` is counted from `PolicyHook.executed`.
    Filtering on `Verdict.allow_silently` instead would report zero savings for a
    household that approved every cancellation it was asked about — the opposite
    of what happened."""
    agent, hook = build(
        store, "cancel_subscription", {"merchant": "FitLife", "monthly_amount_minor": 3800}
    )
    result = agent("cancel it")
    card = persist_decisions(result, store, session_id=SESSION)[0]

    assert hook.executed == []

    agent(build_resume_payload([(card, respond(card, DecisionChoice.APPROVE))]))

    assert [action.kind for action in hook.executed] == [ActionKind.CANCEL_SUBSCRIPTION]


def test_a_denied_action_never_counts_as_executed(store):
    agent, hook = build(
        store, "cancel_subscription", {"merchant": "FitLife", "monthly_amount_minor": 3800}
    )
    result = agent("cancel it")
    card = persist_decisions(result, store, session_id=SESSION)[0]

    agent(build_resume_payload([(card, respond(card, DecisionChoice.DENY))]))

    assert hook.executed == []
