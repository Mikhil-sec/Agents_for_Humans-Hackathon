"""The Lane A -> Lane B seam: generated fixtures must be what the API reads.

`/fixtures` is normally Lane C's, produced by `quiet_hours_integrations.mock.seed`.
That is still a stub, so `make fixtures` falls back to Lane A's exporter and
`make demo` depends on this code path working.

These tests pin the two things that would break it silently:

* **the file names** — Lane B's `api/main.py` asks for five specific files, and a
  missing one is a 404 on a screen rather than an error anyone sees in a build;
* **the shapes** — a list stays a list, because `get_paged_fixture` wraps lists
  into `{items, total, page, size}` and passes anything else straight through.

Everything written is a contract model dumped from the store, so contract
validity is structural rather than something these tests have to check field by
field — but they round-trip one of each anyway, because "it came from the store"
is an argument, not a guarantee.
"""

from __future__ import annotations

import json

import pytest
from quiet_hours_contracts import (
    ActivityEntry,
    DailyBrief,
    DecisionCard,
    DecisionStatus,
    Policy,
    Run,
)

from quiet_hours_agent.export_fixtures import FIXTURE_FILES, export


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    """One export, shared. It runs four weeks of the agent and is slow."""
    root = tmp_path_factory.mktemp("fixtures")
    export(root / "out", store_dir=root / "store", session_dir=root / "sessions")
    return root / "out"


def load(exported, name):
    return json.loads((exported / name).read_text(encoding="utf-8"))


def test_every_file_lane_b_reads_is_produced(exported):
    """`api/main.py` names these five. A sixth appearing there without appearing
    here is a 404 on a screen, not a build failure."""
    for name in FIXTURE_FILES:
        assert (exported / name).exists(), name


def test_the_collection_fixtures_are_lists(exported):
    """`get_paged_fixture` only paginates lists. An object here would reach the
    web app as a bare record where it expected `{items: [...]}`."""
    for name in ("decisions.json", "activity.json", "policies.json", "runs.json"):
        assert isinstance(load(exported, name), list), name


def test_the_brief_is_a_single_object(exported):
    """`/api/brief/latest` returns it unwrapped."""
    assert isinstance(load(exported, "daily_brief.json"), dict)


def test_the_inbox_is_not_empty(exported):
    """An empty inbox is the product working, but it is a poor screenshot — and
    a judge looking at a blank screen cannot tell it apart from a broken one."""
    decisions = load(exported, "decisions.json")

    assert decisions, "the fourth week is left unanswered so a card is pending"
    assert all(card["status"] == DecisionStatus.PENDING.value for card in decisions)


def test_every_record_round_trips_through_its_contract_model(exported):
    """'It came from the store' is an argument, not a guarantee."""
    for card in load(exported, "decisions.json"):
        DecisionCard.model_validate(card)
    for entry in load(exported, "activity.json"):
        ActivityEntry.model_validate(entry)
    for policy in load(exported, "policies.json"):
        Policy.model_validate(policy)
    for run in load(exported, "runs.json"):
        Run.model_validate(run)
    DailyBrief.model_validate(load(exported, "daily_brief.json"))


def test_lane_b_can_look_a_card_up_by_the_id_it_is_given(exported):
    """The exact bug the restore uncovered: the API matched `card["id"]` while
    the contract field is `decision_id`, so every valid card 404'd."""
    for card in load(exported, "decisions.json"):
        assert "decision_id" in card
    for run in load(exported, "runs.json"):
        assert "run_id" in run


def test_the_history_shows_the_agent_learning(exported):
    """The fixtures back the autonomy chart, so they have to contain a story:
    rules that were taught, and a trail that is mostly silent."""
    policies = load(exported, "policies.json")
    activity = load(exported, "activity.json")

    assert policies, "three answered weeks must leave rules behind"
    assert all(p["created_from_decision_id"] for p in policies), "no rule without an answer"

    silent = sum(1 for entry in activity if entry["was_autonomous"])
    assert silent > len(activity) / 2, "most of the trail should be work nobody was asked about"


def test_status_filtering_works_the_way_lane_b_uses_it(exported):
    """`list_decisions` filters on `item["status"] == "pending"` by default."""
    decisions = load(exported, "decisions.json")

    assert [c for c in decisions if c.get("status") == "pending"] == decisions
