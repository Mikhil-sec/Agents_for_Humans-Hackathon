"""A7 — the two things the deployed path persists to that mock mode does not.

`sessions.py` chooses where a suspended run's state lives; `store.DynamoStore`
holds the records Lane B reads. Neither is reachable from `make demo`, which is
exactly why they need tests: the first time anyone runs this for real will be the
day of the deploy, and a mistake in either is invisible until a card cannot be
answered.

Everything here runs against fakes. No AWS calls, no credentials — the same rule
as the rest of the suite.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from quiet_hours_contracts import (
    ActionKind,
    ActivityEntry,
    DecisionCard,
    DecisionChoice,
    DecisionOption,
    DecisionResponse,
    DecisionStatus,
    Evidence,
    Money,
    Policy,
    PolicyScope,
    ProposedAction,
    RiskTier,
    Run,
    RunStatus,
    RunTrigger,
)

from quiet_hours_agent.sessions import (
    SESSION_BUCKET_ENV,
    SessionConfigError,
    build_session_manager,
    session_id_for,
)
from quiet_hours_agent.store import DynamoStore, JsonStore, StoreConfigError, build_store

HOUSEHOLD = "hh_demo"


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


def test_one_session_per_run_not_per_household():
    """A household-wide id rehydrates last Tuesday's conversation into today's run,
    and leaves a spent interrupt state that makes the *next* run fail on resume."""
    assert session_id_for(HOUSEHOLD, "run_a") != session_id_for(HOUSEHOLD, "run_b")
    assert session_id_for(HOUSEHOLD, "run_a").startswith(f"qh-{HOUSEHOLD}")


def test_mock_sessions_go_to_the_directory_they_are_given(tmp_path, monkeypatch):
    monkeypatch.setenv("QH_PROVIDER_MODE", "mock")
    manager = build_session_manager("qh-1", session_dir=tmp_path / "sessions")

    assert (tmp_path / "sessions").exists()
    assert type(manager).__name__ == "FileSessionManager"


def test_live_sessions_without_a_bucket_refuse_to_start(monkeypatch):
    """Deliberately loud. Falling back to local files here produces a system that
    passes every smoke test and silently loses every suspended run: the container
    that writes the session and the one that resumes it share no disk."""
    monkeypatch.delenv(SESSION_BUCKET_ENV, raising=False)

    with pytest.raises(SessionConfigError, match=SESSION_BUCKET_ENV):
        build_session_manager("qh-1", mode="live")


def test_live_sessions_go_to_s3(monkeypatch):
    """Asserted on the arguments rather than the object: `S3SessionManager`
    reaches S3 in its constructor, and this suite has no credentials."""
    import strands.session

    captured: dict = {}

    class FakeS3SessionManager:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(strands.session, "S3SessionManager", FakeS3SessionManager)
    monkeypatch.setenv(SESSION_BUCKET_ENV, "quiet-hours-sessions")
    monkeypatch.setenv("AWS_REGION", "eu-west-2")

    build_session_manager("qh-run-1", mode="live")

    assert captured["bucket"] == "quiet-hours-sessions"
    assert captured["session_id"] == "qh-run-1"
    assert captured["region_name"] == "eu-west-2"
    assert captured["prefix"]


def test_the_session_manager_belongs_on_the_builder_not_a_node_agent():
    """The A5 constraint, restated where the manager is now built.

    Strands raises `ValueError("Session persistence is not supported for Graph
    agents yet.")` if a node executor carries one. `test_graph.py` pins the
    placement; this pins that the note travels with the code that produces it.
    """
    import inspect

    from quiet_hours_agent import sessions

    assert "GraphBuilder.set_session_manager" in inspect.getdoc(sessions) or (
        "never to a node `Agent`" in inspect.getdoc(sessions)
    )


# --------------------------------------------------------------------------
# DynamoStore
# --------------------------------------------------------------------------


class FakeTable:
    """The slice of a boto3 Table resource `DynamoStore` actually uses.

    Query honours `gsi1pk` equality and sorts by `gsi1sk`, which is the whole of
    the index behaviour the store depends on. Anything more would be testing
    DynamoDB rather than our use of it.
    """

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict] = {}

    def put_item(self, *, Item):  # boto3's own casing, kept verbatim
        self.items[(Item["pk"], Item["sk"])] = dict(Item)

    def get_item(self, *, Key):
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": item} if item else {}

    def query(self, *, IndexName, KeyConditionExpression, ScanIndexForward=True):
        assert IndexName == "gsi1"
        wanted = KeyConditionExpression.get_expression()["values"][1]
        matches = [item for item in self.items.values() if item.get("gsi1pk") == wanted]
        matches.sort(key=lambda item: item["gsi1sk"], reverse=not ScanIndexForward)
        return {"Items": matches}


@pytest.fixture
def dynamo() -> DynamoStore:
    return DynamoStore(table_name="quiet-hours", table=FakeTable())


def make_action(action_id: str = "act_1") -> ProposedAction:
    return ProposedAction(
        action_id=action_id,
        household_id=HOUSEHOLD,
        run_id="run_1",
        finding_id="fin_1",
        kind=ActionKind.CANCEL_SUBSCRIPTION,
        summary="Cancel FitLife",
        rationale="No visits in 90 days.",
        params={"merchant": "FitLife"},
        risk=RiskTier.CONFIRM,
        evidence=[Evidence(signal_id="sig_1", excerpt="FITLIFE GYM MEMBERSHIP")],
        created_at=datetime.now(UTC),
    )


def make_card(decision_id: str = "dec_1", *, status=DecisionStatus.PENDING) -> DecisionCard:
    return DecisionCard(
        decision_id=decision_id,
        household_id=HOUSEHOLD,
        run_id="run_1",
        action_id="act_1",
        session_id="qh-hh_demo-run_1",
        interrupt_id="v1:before_tool_call:tooluse_1:abc",
        interrupt_name="qh-approval",
        headline="FitLife is about to charge you £38",
        body="No visit recorded in 90 days.",
        why_asking="This cancels a service and no policy covers fitness subscriptions.",
        options=[
            DecisionOption(choice=DecisionChoice.APPROVE, label="Cancel it"),
            DecisionOption(choice=DecisionChoice.DENY, label="Keep it"),
        ],
        amount=Money(amount_minor=3800, currency="GBP"),
        evidence=[Evidence(signal_id="sig_1", excerpt="FITLIFE GYM MEMBERSHIP £38.00")],
        status=status,
        created_at=datetime.now(UTC),
    )


def make_entry(entry_id: str, *, when: datetime) -> ActivityEntry:
    return ActivityEntry(
        entry_id=entry_id,
        household_id=HOUSEHOLD,
        run_id="run_1",
        action_id="act_1",
        occurred_at=when,
        summary=f"Did {entry_id}",
        rationale="Routine.",
        risk=RiskTier.SILENT,
        was_autonomous=True,
        succeeded=True,
    )


def test_records_round_trip_as_the_frozen_contract_shape(dynamo):
    """Stored as JSON text, not as attributes.

    DynamoDB has no float type and `Finding.confidence` is a float. Storing
    attributes would mean a `Decimal` conversion on every write and back on every
    read, in both Lane A's code and Lane B's, forever. The bytes in the table are
    exactly what `model_dump_json` produced, so both lanes parse them with the
    same pydantic models.
    """
    card = make_card()
    dynamo.save_decision(card)

    assert dynamo.get_decision("dec_1") == card


def test_ids_are_looked_up_without_a_household(dynamo):
    """`Store.get_decision` takes no `household_id` — Lane B's respond endpoint
    only has the id from the URL. That is why the id is the partition key."""
    dynamo.save_decision(make_card())
    dynamo.put_action(make_action())
    dynamo.save_run(
        Run(
            run_id="run_1",
            household_id=HOUSEHOLD,
            trigger=RunTrigger.SCHEDULE,
            status=RunStatus.COMPLETED,
            session_id="qh-hh_demo-run_1",
            started_at=datetime.now(UTC),
        )
    )

    assert dynamo.get_decision("dec_1") is not None
    assert dynamo.get_action("act_1") is not None
    assert dynamo.get_run("run_1") is not None


def test_a_missing_record_is_none_not_an_error(dynamo):
    assert dynamo.get_decision("dec_nope") is None
    assert dynamo.get_action("act_nope") is None
    assert dynamo.get_run("run_nope") is None


def test_household_queries_do_not_leak_across_tenancy(dynamo):
    dynamo.save_decision(make_card("dec_ours"))

    theirs = make_card("dec_theirs")
    theirs.household_id = "hh_someone_else"
    dynamo.save_decision(theirs)

    pending = dynamo.list_pending_decisions(HOUSEHOLD)
    assert [card.decision_id for card in pending] == ["dec_ours"]


def test_only_pending_decisions_reach_the_inbox(dynamo):
    dynamo.save_decision(make_card("dec_open"))
    dynamo.save_decision(make_card("dec_done", status=DecisionStatus.RESOLVED))

    assert [card.decision_id for card in dynamo.list_pending_decisions(HOUSEHOLD)] == ["dec_open"]


def test_resolving_a_card_keeps_it_in_one_partition(dynamo):
    """Status is filtered, never folded into the key. Putting it in `gsi1pk` would
    make resolving a card a delete-and-reinsert across two partitions, and a crash
    between the two would lose the card entirely."""
    dynamo.save_decision(make_card())
    response = DecisionResponse(
        decision_id="dec_1", choice=DecisionChoice.APPROVE, responded_at=datetime.now(UTC)
    )

    resolved = dynamo.resolve_decision("dec_1", response)

    assert resolved.status is DecisionStatus.RESOLVED
    assert dynamo.get_decision("dec_1").status is DecisionStatus.RESOLVED
    assert dynamo.list_pending_decisions(HOUSEHOLD) == []


def test_resolving_an_unknown_card_is_reported_not_raised(dynamo):
    """The hook replays this on resume, so it has to be idempotent and forgiving."""
    response = DecisionResponse(
        decision_id="dec_nope", choice=DecisionChoice.APPROVE, responded_at=datetime.now(UTC)
    )
    assert dynamo.resolve_decision("dec_nope", response) is None


def test_the_activity_trail_comes_back_in_order(dynamo):
    """`gsi1sk` is `occurred_at`, so the index returns these already sorted — the
    trail is read as a narrative and an out-of-order one reads as a bug."""
    base = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    for offset, entry_id in enumerate(["ent_c", "ent_a", "ent_b"]):
        dynamo.write_activity(make_entry(entry_id, when=base.replace(hour=9 + offset)))

    assert [entry.entry_id for entry in dynamo.list_activity(HOUSEHOLD)] == [
        "ent_c",
        "ent_a",
        "ent_b",
    ]


def test_policies_round_trip(dynamo):
    policy = Policy(
        policy_id="pol_1",
        household_id=HOUSEHOLD,
        scope=PolicyScope.MERCHANT,
        action_kind=ActionKind.CANCEL_SUBSCRIPTION,
        merchant="FitLife",
        effect="auto_approve",
        description="Cancel FitLife subscriptions without asking",
        created_at=datetime.now(UTC),
    )
    dynamo.save_policy(policy)

    assert dynamo.list_policies(HOUSEHOLD) == [policy]
    assert dynamo.list_policies("hh_someone_else") == []


def test_the_store_satisfies_the_same_protocol_as_the_json_one():
    """Lane B reads what this writes, so the two implementations must not drift."""
    for name in (
        "put_action",
        "get_action",
        "save_decision",
        "get_decision",
        "resolve_decision",
        "list_pending_decisions",
        "write_activity",
        "list_activity",
        "list_policies",
        "save_policy",
        "save_run",
        "get_run",
    ):
        assert callable(getattr(DynamoStore, name)), name
        assert callable(getattr(JsonStore, name)), name


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------


def test_mock_mode_still_gets_the_json_store(monkeypatch, tmp_path):
    monkeypatch.setenv("QH_STORE_DIR", str(tmp_path))
    assert isinstance(build_store("mock"), JsonStore)


def test_live_without_a_table_name_refuses_to_start(monkeypatch):
    monkeypatch.delenv("QH_TABLE_NAME", raising=False)
    with pytest.raises(StoreConfigError, match="QH_TABLE_NAME"):
        build_store("live")
