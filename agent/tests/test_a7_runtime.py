"""A7 — the AgentCore entrypoint.

`main.py` is the deployed twin of `local_run.py`: same graph, same policy gate,
same store, reached over HTTP instead of a terminal. These tests exercise the
cycle underneath the HTTP surface, which is where all the behaviour lives.

Three things are worth failing the build over and each has a test named after it:

* **The whole stream is JSON.** AgentCore serialises every yielded event into an
  SSE body. A `GraphResult` in there fails inside the platform's writer, not in
  our code, which is the worst place to find out.
* **A resume uses the card's session id**, never the runtime's. They are
  different identifiers with the same name and mixing them up produces a run that
  starts cleanly and resumes nothing.
* **No credentials are needed.** Same rule as `test_local_run.py`.

`pytest-asyncio` is deliberately not used. It is declared in `pyproject.toml` but
not installed in the dev environment, and adding a plugin to the critical path of
`make demo` for four tests is a bad trade — `collect()` below is the whole of
what it would have provided.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest
from quiet_hours_contracts import DecisionChoice, DecisionResponse, DecisionStatus, RunStatus

from quiet_hours_agent import main
from quiet_hours_agent.store import JsonStore

HOUSEHOLD = "hh_demo"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Point the store and sessions at a temp dir, never the developer's."""
    monkeypatch.setenv("QH_STORE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("QH_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("QH_PROVIDER_MODE", "mock")
    return tmp_path


@pytest.fixture
def store(isolated_state):
    return JsonStore(isolated_state / "store")


def collect(payload: dict) -> list[dict]:
    """Drain the entrypoint into a list of envelopes."""

    async def drain() -> list[dict]:
        return [event async for event in main.invoke(payload)]

    return asyncio.run(drain())


def of_type(events: list[dict], kind: str) -> list[dict]:
    return [event for event in events if event.get("type") == kind]


def only(events: list[dict], kind: str) -> dict:
    matches = of_type(events, kind)
    assert len(matches) == 1, f"expected exactly one {kind}, got {len(matches)}"
    return matches[0]


# --------------------------------------------------------------------------
# A scheduled run
# --------------------------------------------------------------------------


def test_scheduled_run_streams_progress_and_stops_to_ask(store):
    """The A1/A5 mechanic, over the entrypoint: some work silent, one thing asked."""
    events = collect({"household_id": HOUSEHOLD})

    started = only(events, "run_started")
    assert started["household_id"] == HOUSEHOLD
    # One session per run, not per household — see `sessions.session_id_for`.
    assert started["session_id"] == f"qh-{HOUSEHOLD}-{started['run_id']}"

    # Progress, not prose — the inbox is not a chat surface.
    assert {event["node"] for event in of_type(events, "node_started")} >= {"ingest", "triage"}

    cards = of_type(events, "decision_required")
    assert cards, "the run should have stopped to ask about the spend"

    finished = only(events, "run_finished")
    assert finished["status"] == RunStatus.WAITING_ON_USER.value
    assert finished["stats"]["actions_autonomous"] >= 1, "routine work must stay silent"
    assert finished["decisions"] == [card["decision"]["decision_id"] for card in cards]


def test_the_stats_are_counted_not_estimated(store):
    """Lane B's autonomy chart reads these, so every field has to be populated
    from something measured. `signals_ingested` comes off `invocation_state`,
    where the ungoverned `load_signals` tool stashes the real `Signal` objects;
    `findings_created` off the harvest. Both sat at zero until A7 wired them.
    """
    events = collect({"household_id": HOUSEHOLD})
    stats = only(events, "run_finished")["stats"]

    assert stats["signals_ingested"] > 0
    assert stats["findings_created"] == len(only(events, "run_finished")["findings"])
    assert stats["actions_proposed"] == stats["actions_autonomous"] + stats["decisions_raised"]


def test_every_streamed_event_is_json_serialisable():
    """AgentCore writes these into an SSE body. A Strands object there fails in the
    platform's writer, where the traceback is least useful."""
    for event in collect({"household_id": HOUSEHOLD}):
        json.dumps(event)  # raises TypeError on a NodeResult or a GraphResult


def test_mock_mode_needs_no_credentials(monkeypatch, store):
    """The judge's path, and the deployed path's own smoke test."""
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "AWS_REGION"):
        monkeypatch.delenv(name, raising=False)

    finished = only(collect({"household_id": HOUSEHOLD}), "run_finished")
    assert finished["status"] in {
        RunStatus.WAITING_ON_USER.value,
        RunStatus.COMPLETED.value,
    }


def test_a_run_persists_its_cards_so_the_api_can_serve_them(store):
    """The stream is a convenience; the store is the contract with Lane B."""
    collect({"household_id": HOUSEHOLD})

    pending = store.list_pending_decisions(HOUSEHOLD)
    assert pending, "a suspended run must leave an answerable card behind"
    assert all(card.status is DecisionStatus.PENDING for card in pending)
    assert all(card.session_id.startswith(f"qh-{HOUSEHOLD}-") for card in pending)


def test_a_second_run_does_not_trample_a_suspended_one(store):
    """A household waiting on a human is not eligible for a fresh run.

    A second run would pile more cards onto an inbox nobody has answered and
    spend another run's worth of tokens re-reasoning about the same unresolved
    day. It reports what is outstanding instead.
    """
    first = collect({"household_id": HOUSEHOLD})
    first_ids = [card["decision"]["decision_id"] for card in of_type(first, "decision_required")]

    second = collect({"household_id": HOUSEHOLD})

    assert not of_type(second, "run_started"), "no new run should have been started"
    assert [
        card["decision"]["decision_id"] for card in of_type(second, "decision_required")
    ] == first_ids
    assert only(second, "run_finished")["status"] == RunStatus.WAITING_ON_USER.value


# --------------------------------------------------------------------------
# Resuming
# --------------------------------------------------------------------------


def _answer(card_id: str, choice: DecisionChoice) -> dict:
    return DecisionResponse(
        decision_id=card_id,
        choice=choice,
        responded_at=datetime.now(UTC),
    ).model_dump(mode="json")


def test_resume_completes_the_suspended_tool_call(store):
    """The point of the whole module: a new invocation finishes the old call."""
    collect({"household_id": HOUSEHOLD})
    pending = store.list_pending_decisions(HOUSEHOLD)
    assert pending

    events = collect(
        {
            "household_id": HOUSEHOLD,
            "decision_responses": [_answer(pending[0].decision_id, DecisionChoice.APPROVE)],
        }
    )

    assert only(events, "run_started")["resumed_from"] == [pending[0].decision_id]
    assert only(events, "run_finished")["status"] == RunStatus.COMPLETED.value
    assert store.get_decision(pending[0].decision_id).status is DecisionStatus.RESOLVED


def test_resume_uses_the_cards_session_id_not_the_runtimes(store):
    """Two identifiers share the name `session_id` and only one resumes anything.

    AgentCore's runtime session id names *this HTTP conversation*. The Strands
    session id names the suspended graph and was written days earlier. Reading it
    off the payload — or off `context` — would build a graph over a session that
    has never been written to, and the resume would raise `no interrupt found`.
    """
    collect({"household_id": HOUSEHOLD})
    card = store.list_pending_decisions(HOUSEHOLD)[0]

    events = collect(
        {
            "household_id": HOUSEHOLD,
            "session_id": "runtime-session-abc123",  # AgentCore's, deliberately wrong
            "decision_responses": [_answer(card.decision_id, DecisionChoice.APPROVE)],
        }
    )

    assert only(events, "run_started")["session_id"] == card.session_id
    assert only(events, "run_finished")["status"] == RunStatus.COMPLETED.value


def test_approve_always_learns_a_rule_that_stops_the_asking(store):
    """The autonomy curve, over the entrypoint rather than the CLI."""
    collect({"household_id": HOUSEHOLD})
    card = store.list_pending_decisions(HOUSEHOLD)[0]

    assert not store.list_policies(HOUSEHOLD)
    collect(
        {
            "household_id": HOUSEHOLD,
            "decision_responses": [_answer(card.decision_id, DecisionChoice.APPROVE_ALWAYS)],
        }
    )
    assert store.list_policies(HOUSEHOLD), "APPROVE_ALWAYS must create a policy"

    events = collect({"household_id": HOUSEHOLD})
    finished = only(events, "run_finished")

    assert not of_type(events, "decision_required"), "the learned rule should cover this"
    assert finished["status"] == RunStatus.COMPLETED.value
    assert finished["stats"]["actions_autonomous"] == finished["stats"]["actions_proposed"]
    assert finished["stats"]["policies_applied"] >= 1


def test_a_single_decision_response_is_accepted(store):
    """Lane B's endpoint answers one card at a time; the graph can suspend on more
    than one. Both the singular and plural keys have to work."""
    collect({"household_id": HOUSEHOLD})
    card = store.list_pending_decisions(HOUSEHOLD)[0]

    events = collect(
        {
            "household_id": HOUSEHOLD,
            "decision_response": _answer(card.decision_id, DecisionChoice.APPROVE),
        }
    )
    assert only(events, "run_finished")["status"] == RunStatus.COMPLETED.value


# --------------------------------------------------------------------------
# Failure modes
# --------------------------------------------------------------------------


def test_a_bad_payload_yields_an_error_envelope_rather_than_raising():
    """A raise mid-stream reaches the client as a truncated SSE body with no
    status code, and 'the connection ended' is not something an inbox can render."""
    error = only(collect({}), "error")
    assert error["error"] == "bad_payload"
    assert "household_id" in error["message"]


def test_an_unknown_decision_id_is_reported_not_swallowed(store):
    error = only(
        collect({"decision_responses": [_answer("dec_does_not_exist", DecisionChoice.APPROVE)]}),
        "error",
    )
    assert error["error"] == "bad_payload"
    assert "dec_does_not_exist" in error["message"]


def test_importing_main_does_not_require_bedrock_agentcore():
    """`bedrock-agentcore` is needed to *serve* this module, not to run the cycle.

    Requiring it at import would put an AWS SDK between a judge and `make demo`,
    and would break this suite, which has no AWS packages installed at all.
    """
    assert main.run_cycle is not None
    assert main.app is None or hasattr(main.app, "run")
