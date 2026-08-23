"""`make agent` — the demo a judge actually runs.

Root `AGENTS.md` rule 3: mock mode must always work with zero credentials, and a
change that breaks it is the wrong change. This file is that rule as a test.

It asserts the three-command story end to end:

    run          -> routine work handled silently, the spend stops to ask
    --answer     -> the suspended run resumes and completes
    run again    -> the learned rule means nothing needs the user

That last transition — 2/3 silent becoming 4/4 silent — is the product thesis,
so it is worth failing the build over.

The counts moved when A5 landed: the run is now a six-node graph over four
signals rather than a single agent over two hard-coded tool calls, so a full run
touches more actions. The *shape* being asserted is unchanged, and it is the
shape that matters — some work is silent, exactly one thing asks, and after the
user answers once it stops asking.
"""

from __future__ import annotations

import pytest
from quiet_hours_contracts import DecisionStatus

from quiet_hours_agent import local_run
from quiet_hours_agent.store import JsonStore

HOUSEHOLD = "hh_demo"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Point the store and sessions at a temp dir, never the developer's."""
    monkeypatch.setenv("QH_STORE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("QH_PROVIDER_MODE", "mock")
    return tmp_path


@pytest.fixture
def store(isolated_state):
    return JsonStore(isolated_state / "store")


def test_mock_mode_needs_no_credentials(monkeypatch, store, capsys):
    """The judge's path: no AWS anything in the environment."""
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "AWS_REGION"):
        monkeypatch.delenv(name, raising=False)

    assert local_run.main([]) == 0
    assert "Quiet Hours" in capsys.readouterr().out


def test_the_three_command_demo(store, capsys):
    # 1. A fresh run: routine work happens, the spend stops to ask.
    assert local_run.main([]) == 0
    first = capsys.readouterr().out
    assert "DECISION NEEDED" in first
    assert "2/3 handled silently" in first

    pending = store.list_pending_decisions(HOUSEHOLD)
    assert len(pending) == 1
    assert pending[0].why_asking

    # 2. Answering resumes the suspended run and teaches a rule.
    assert local_run.main(["--answer", "approve_always"]) == 0
    second = capsys.readouterr().out
    assert "Run completed." in second
    assert "New rule learned" in second

    assert store.get_decision(pending[0].decision_id).status is DecisionStatus.RESOLVED
    assert len(store.list_policies(HOUSEHOLD)) == 1

    # 3. The same work again, now covered by the rule. This is the whole pitch.
    assert local_run.main([]) == 0
    third = capsys.readouterr().out
    assert "Nothing needs you today." in third
    assert "4/4 actions handled silently" in third
    assert "DECISION NEEDED" not in third


def test_denying_leaves_no_policy_and_runs_the_tool_never(store, capsys):
    local_run.main([])
    capsys.readouterr()

    assert local_run.main(["--answer", "deny"]) == 0
    out = capsys.readouterr().out
    assert "New rule learned" not in out
    assert store.list_policies(HOUSEHOLD) == []

    failed = [entry for entry in store.list_activity(HOUSEHOLD) if not entry.succeeded]
    assert len(failed) == 1
    assert "declined" in (failed[0].error or "").casefold()


def test_a_second_run_refuses_to_stack_on_an_unanswered_decision(store, capsys):
    local_run.main([])
    capsys.readouterr()

    assert local_run.main([]) == 0
    out = capsys.readouterr().out
    assert "already waiting" in out
    assert len(store.list_pending_decisions(HOUSEHOLD)) == 1


def test_reset_clears_everything(store, capsys):
    local_run.main([])
    capsys.readouterr()
    assert store.list_pending_decisions(HOUSEHOLD)

    assert local_run.main(["--reset"]) == 0
    assert JsonStore(local_run.store_root()).list_pending_decisions(HOUSEHOLD) == []


def test_every_action_is_audited_even_the_silent_one(store):
    """`agent/AGENTS.md` rule 3 — nothing happens invisibly."""
    local_run.main([])
    local_run.main(["--answer", "approve"])

    entries = store.list_activity(HOUSEHOLD)

    # One line per action the graph took, across both processes: three handled
    # silently and the one the user was asked about.
    assert len(entries) == 4
    assert {entry.was_autonomous for entry in entries} == {True, False}
    assert sum(1 for entry in entries if not entry.was_autonomous) == 1
    assert all(entry.rationale for entry in entries)

    # Every entry belongs to a real action and names the run that produced it,
    # which is what makes the trail auditable rather than merely present.
    assert all(entry.action_id and entry.run_id for entry in entries)


def test_the_silent_work_is_not_repeated_when_the_run_resumes(store):
    """A resumed graph replays the interrupted node only.

    Strands keeps completed nodes completed across a suspension, so the actions
    they already took must not happen twice. If this regresses, the user's
    activity trail double-counts and the autonomy rate is computed off inflated
    numbers — both silent, both corrosive.
    """
    local_run.main([])
    before = store.list_activity(HOUSEHOLD)
    silent_before = [entry.summary for entry in before if entry.was_autonomous]

    local_run.main(["--answer", "approve"])
    after = store.list_activity(HOUSEHOLD)

    # The bill record and the reminder happened before the interrupt; after the
    # resume they should still appear exactly once each.
    for summary in silent_before:
        assert sum(1 for entry in after if entry.summary == summary) == 1
