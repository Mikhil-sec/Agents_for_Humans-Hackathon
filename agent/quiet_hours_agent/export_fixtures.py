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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quiet_hours_contracts import DecisionChoice

from .graph import build_graph, harvest
from .replay import WEEKS, replay
from .resume import persist_decisions, was_interrupted
from .store import JsonStore, new_id

logger = logging.getLogger(__name__)

HOUSEHOLD = "hh_demo"

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
        start=datetime(2026, 8, 1, tzinfo=UTC),
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
    result = run("Do this household's admin for today.")
    if was_interrupted(result):
        persist_decisions(result, store, session_id=session_id)

    return harvest(result, run, pending_decision_ids=[])


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
