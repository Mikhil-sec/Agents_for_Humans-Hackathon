"""Generate `/fixtures` from a real agent run.

    python -m quiet_hours_agent.export_fixtures --out fixtures/

## Why this exists

Lane B's API reads static JSON out of `/fixtures` so that every screen can be
built without the agent running — and `make demo` serves those files to a judge.
Producing them is Lane C's `quiet_hours_integrations.mock.seed`, which is still a
stub, so `make fixtures` fails and the whole demo chain is dead at step one.

This is Lane A's fallback for that. It is **not** a reimplementation of Lane C's
seeder: it does not invent an inbox, and it reads nothing from `/fixtures`. It
runs the agent for real, in mock mode, and writes out what the run actually
produced.

## Why generating beats hand-writing

Hand-written fixtures drift from the contract the moment a model changes, and
they drift silently — the API happily serves a `DecisionCard` missing a field
nobody noticed. Everything written here came out of `store.py`, which only ever
holds validated contract models, so the fixtures are contract-correct by
construction. If `/contracts` changes, regenerate and they are correct again.

## The state it produces

Three weeks of history are replayed and answered, then a fourth week is run and
**deliberately left unanswered**. That is the interesting state to render:

* `policies.json`   — rules the household actually taught the agent
* `activity.json`   — three weeks of audit trail, most of it silent
* `runs.json`       — the per-run stats behind the autonomy chart
* `decisions.json`  — a live pending card, so the inbox is not empty
* `daily_brief.json`— the digest for the final run

An inbox with nothing in it is the product working, but it is a poor screenshot.

Lane C's real fixtures replace these when they land. Nothing in Lane A reads
them back — `signals.py` has its own stand-in — so there is no circularity.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from quiet_hours_contracts import DecisionChoice, Run, RunTrigger

from .graph import build_graph, harvest, summarise_run
from .replay import WEEKS, replay
from .resume import persist_decisions, run_status_for, was_interrupted
from .store import JsonStore, new_id

logger = logging.getLogger(__name__)

HOUSEHOLD = "hh_demo"

REPLAY_START = datetime(2026, 8, 1, tzinfo=UTC)
"""Week 1's date. Weeks 2-4 follow at weekly intervals, and the autonomy chart
plots each run along that axis — so the fourth week's `Run` has to be dated from
here too, not from wall clock."""


class EmptyRunError(RuntimeError):
    """The export run produced no signals. See `_require_signals`."""


FIXTURE_FILES = (
    "decisions.json",
    "activity.json",
    "policies.json",
    "runs.json",
    "daily_brief.json",
)
"""Exactly what `api/main.py` asks for. Kept as a tuple so the test that pins
this list fails loudly if Lane B starts reading a sixth file."""


def _dump(path: Path, payload: Any) -> None:
    """Write one fixture. A list stays a list — Lane B's `get_paged_fixture`
    wraps lists into `{items, total, page, size}` and passes anything else
    through, so the shape here decides the shape of the API response."""
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("wrote %s", path.name)


def build_state(store: JsonStore, session_dir: Path) -> Any:
    """Three answered weeks, then one left open.

    The replay is the honest way to produce policies and audit history: every
    rule in the output was created by an answer, exactly as it would be in
    production. Hand-seeding policies would produce a policies page full of
    rules no decision ever justified, which is the one thing that page must
    never show.
    """
    replay(
        HOUSEHOLD,
        store=store,
        session_dir=session_dir,
        weeks=WEEKS[:3],
        answer=DecisionChoice.APPROVE_ALWAYS,
        start=REPLAY_START,
    )

    # The fourth week runs but is never answered, so its cards stay pending and
    # the inbox has something to show.
    run_id = new_id("run")
    session_id = f"qh-{HOUSEHOLD}-{run_id}"
    run = build_graph(
        HOUSEHOLD,
        store=store,
        run_id=run_id,
        session_id=session_id,
        session_dir=session_dir,
        mode="mock",
        scenario=WEEKS[3].key,
    )
    # **The fourth week continues the series; it is not "now".** `replay` dates
    # week N at `REPLAY_START + N weeks`, and the autonomy chart plots runs along
    # that axis. Stamping this one with `utcnow()` put the final point weeks after
    # the other three — the chart read "1 Aug, 8 Aug, 15 Aug, 7 Sept", with a gap
    # that says the agent sat idle for a fortnight. Caught by looking at the
    # rendered Insights page, not by any test.
    started_at = REPLAY_START + timedelta(weeks=3)
    result = run("Do this household's admin for today.")

    # **Keep the cards.** `harvest` was called with `pending_decision_ids=[]`, so
    # the brief announced "Nothing needs you today" while a card sat pending in
    # the same fixture set. Lane B renders the brief headline above the inbox,
    # so the demo's first screen contradicted itself.
    cards = (
        persist_decisions(result, store, session_id=session_id) if was_interrupted(result) else []
    )

    outcome = harvest(result, run, pending_decision_ids=[card.decision_id for card in cards])

    # **The fourth week needs a `Run` record like the other three.** `save_run`
    # was only ever called from `replay.py`, and this week does not go through
    # it — so `runs.json` held three runs and stopped one short of the point the
    # autonomy chart is drawn to make, while `decisions.json` carried a pending
    # card whose `run_id` matched no run in the file. Lane B renders both from
    # these fixtures; a card pointing at a missing run is a broken link on the
    # one screen a judge is guaranteed to open.
    interrupted = was_interrupted(result)
    store.save_run(
        Run(
            run_id=run_id,
            household_id=HOUSEHOLD,
            trigger=RunTrigger.SCHEDULE,
            status=run_status_for(result),
            session_id=session_id,
            started_at=started_at,
            # An interrupted run has not finished — it is waiting on the user,
            # which is the whole state this week exists to show.
            finished_at=None if interrupted else started_at,
            stats=summarise_run(run, outcome),
        )
    )

    _require_signals(run)
    return outcome


def _require_signals(run: Any) -> None:
    """Refuse to export a fixture set generated from an empty day.

    Zero signals is not an exception anywhere it passes through: the providers
    return three empty lists, triage finds nothing, no specialist wakes, and
    `RunStats.autonomy_rate` scores zero actions as a perfect **1.0**. The export
    then writes an empty inbox, an empty trail and a flawless autonomy figure,
    and every one of those files is contract-valid. It looks like a quiet day.

    The way it actually happens is a clock mismatch — a read window anchored to
    wall clock against a fixture world anchored to a fixed date (see
    `signals.resolve_now`). That is a defect, and a defect that publishes itself
    as a perfect score is the worst kind this codebase can produce.
    """
    signals = run.invocation_state.get("signals") or []
    if signals:
        return
    raise EmptyRunError(
        "the export run ingested no signals, so every fixture it would write is "
        "an empty day with a 1.0 autonomy rate. Check that /fixtures is seeded "
        "and that the read window is anchored to the fixture world's clock — "
        "see signals.resolve_now."
    )


def export(out_dir: Path, *, store_dir: Path, session_dir: Path) -> list[Path]:
    """Run the agent and write the fixture set. Returns the files written."""
    for path in (store_dir, session_dir):
        shutil.rmtree(path, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    store = JsonStore(store_dir)
    outcome = build_state(store, session_dir)

    decisions = store.list_pending_decisions(HOUSEHOLD)
    activity = store.list_activity(HOUSEHOLD)
    policies = store.list_policies(HOUSEHOLD)

    runs = []
    for path in sorted((store_dir / "runs").glob("*.json")):
        runs.append(json.loads(path.read_text(encoding="utf-8")))
    runs.sort(key=lambda run: run.get("started_at") or "")

    _dump(out_dir / "decisions.json", [card.model_dump(mode="json") for card in decisions])
    _dump(out_dir / "activity.json", [entry.model_dump(mode="json") for entry in activity])
    _dump(out_dir / "policies.json", [policy.model_dump(mode="json") for policy in policies])
    _dump(out_dir / "runs.json", runs)
    _dump(
        out_dir / "daily_brief.json",
        outcome.brief.model_dump(mode="json") if outcome.brief else {},
    )

    print(
        f"  {len(decisions)} pending decision(s), {len(activity)} activity entries, "
        f"{len(policies)} learned rule(s), {len(runs)} run(s)"
    )
    return [out_dir / name for name in FIXTURE_FILES]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quiet-hours-export-fixtures",
        description="Generate /fixtures from a real mock-mode agent run.",
    )
    parser.add_argument("--out", default="fixtures", help="Where to write the fixture set.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    out_dir = Path(args.out)
    scratch = out_dir.parent / ".local" / "export"

    print(f"Generating fixtures from a real agent run -> {out_dir}/")
    written = export(
        out_dir,
        store_dir=scratch / "store",
        session_dir=scratch / "sessions",
    )
    shutil.rmtree(scratch, ignore_errors=True)

    for path in written:
        print(f"    {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
