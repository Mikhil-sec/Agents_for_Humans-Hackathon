"""`make agent` — run one cycle locally in mock mode.

Must work with **zero credentials**. This is what a hackathon judge runs, and it
is the fastest inner loop for Lane A.

    QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run
    QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run --answer approve_always
    QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run --reset

The three commands above are the demo, in order:

1. The graph ingests the day's signals, triages them, wakes only the specialists
   that have something to do, handles the routine work **silently**, and **stops
   to ask** about the one thing that spends money. It exits, leaving a resumable
   session on disk.
2. Answering resumes that exact graph — in a *new process* — and completes the
   action. `approve_always` also creates a policy.
3. Run it again and the same decision no longer interrupts. That fall in the
   interrupt rate is the product.

Scope: this is the real graph (A5) over the real policy gate, store and resume
path (A1 + A3). What is still mocked is the *reasoning* (`mock_reasoning.py`,
because mock mode has no Bedrock) and the *signals* (`signals.py`, because Lane
C's providers are A4).
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from quiet_hours_contracts import (
    DecisionCard,
    DecisionChoice,
    DecisionResponse,
    Run,
    RunStats,
    RunStatus,
    RunTrigger,
)

from .graph import GraphRun, build_graph, harvest
from .resume import build_resume_payload, persist_decisions, run_status_for, was_interrupted
from .store import DEFAULT_STORE_DIR, JsonStore, build_store, new_id, utcnow

logger = logging.getLogger(__name__)


def store_root() -> Path:
    return Path(os.environ.get("QH_STORE_DIR") or DEFAULT_STORE_DIR)


def session_root() -> Path:
    """Where Strands sessions live - beside the store, so both move together.

    Resolved per call rather than at import so `QH_STORE_DIR` actually takes
    effect for the tests and for anyone running two households side by side.
    """
    return store_root().parent / "sessions"


def build_run(household_id: str, store: JsonStore, *, session_id: str, run_id: str) -> GraphRun:
    """The graph and its policy gate. Identical when starting or resuming a run.

    Resuming *requires* this to be identical — the second process rehydrates the
    first one's suspended state by session id, so a graph assembled differently
    would not line up with what is on disk.
    """
    return build_graph(
        household_id,
        store=store,
        run_id=run_id,
        session_id=session_id,
        session_dir=session_root(),
        mode=os.environ.get("QH_PROVIDER_MODE", "mock"),
    )


def _print_cards(cards: list[DecisionCard]) -> None:
    for card in cards:
        print(f"\n  +-- DECISION NEEDED - {card.decision_id}")
        print(f"  | {card.headline}")
        print(f"  | {card.body}")
        print(f"  | Why asking: {card.why_asking}")
        for option in card.options:
            preview = (
                f"  ({option.creates_policy_preview})" if option.creates_policy_preview else ""
            )
            print(f"  |   [{option.choice.value}] {option.label}{preview}")
        print("  +-- answer with: --answer approve | approve_always | deny")


def _print_findings(findings) -> None:
    """What the graph concluded, before it did anything about it."""
    if not findings:
        return
    print("\n  What Quiet Hours found:")
    for finding in findings:
        print(f"    - [{finding.kind.value}] {finding.title}  (confidence {finding.confidence:.2f})")


def _print_activity(store: JsonStore, household_id: str, run_id: str | None = None) -> None:
    """Show this run's audit lines.

    The stored trail is cumulative — that is the product promise — but the
    console is not, because what a judge wants to see is what *this* run did.
    """
    entries = store.list_activity(household_id)
    if run_id is not None:
        entries = [entry for entry in entries if entry.run_id == run_id]
    if not entries:
        return
    print("\n  Activity trail (every action, silent or not):")
    for entry in entries:
        mark = "auto " if entry.was_autonomous else "asked"
        state = "ok " if entry.succeeded else "no "
        print(f"    {state} {mark}  {entry.summary}")
        print(f"              {entry.rationale}")


def _print_brief(brief) -> None:
    if brief is None:
        return
    print(f"\n  Your brief: {brief.headline}")
    for line in brief.handled_silently:
        print(f"    - {line}")


def _summarise(run: GraphRun) -> RunStats:
    verdicts = run.policy_hook.verdicts
    proposed = len(verdicts)
    autonomous = sum(1 for _, verdict in verdicts if verdict.allow_silently)
    return RunStats(
        actions_proposed=proposed,
        actions_autonomous=autonomous,
        decisions_raised=proposed - autonomous,
        policies_applied=sum(1 for _, verdict in verdicts if verdict.policy_id),
    )


def _save_run(store: JsonStore, run: GraphRun, *, session_id: str, result, stats: RunStats) -> None:
    interrupted = was_interrupted(result)
    store.save_run(
        Run(
            run_id=run.run_id,
            household_id=run.household_id,
            trigger=RunTrigger.MANUAL,
            status=run_status_for(result),
            session_id=session_id,
            started_at=utcnow(),
            finished_at=None if interrupted else utcnow(),
            stats=stats,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quiet-hours-agent")
    parser.add_argument("--household", default="hh_demo")
    parser.add_argument(
        "--answer",
        choices=[choice.value for choice in DecisionChoice],
        help="Answer every pending decision and resume the suspended run.",
    )
    parser.add_argument(
        "--reset", action="store_true", help="Wipe local store and sessions, then exit."
    )
    parser.add_argument(
        "--replay-weeks",
        type=int,
        default=0,
        help="Replay N weeks of seeded history to produce the autonomy curve (A6).",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    # Windows consoles default to cp1252 and will crash on text that came from a
    # contract field (merchant names, em-dashes in summaries). The data is right;
    # it is the terminal that is narrow. Never let printing break a judge's demo.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    mode = os.environ.get("QH_PROVIDER_MODE", "mock")
    if mode != "mock" and not os.environ.get("AWS_REGION"):
        print(
            "live mode needs AWS_REGION; set QH_PROVIDER_MODE=mock to run offline", file=sys.stderr
        )
        return 2

    if args.reset:
        for path in (store_root(), session_root()):
            shutil.rmtree(path, ignore_errors=True)
        print("Reset local store and sessions.")
        return 0

    if args.replay_weeks:
        print("--replay-weeks is A6 and needs Lane C's four-week fixtures. Not implemented yet.")
        return 2

    store = build_store(mode)
    assert isinstance(store, JsonStore)

    household = args.household
    session_id = f"qh-{household}"
    print(f"Quiet Hours - household={household} mode={mode}")

    policies = store.list_policies(household)
    if policies:
        print(f"  {len(policies)} learned rule(s) in force:")
        for policy in policies:
            print(f"    - {policy.description}")

    pending = store.list_pending_decisions(household)

    # ---- resume path -----------------------------------------------------
    if args.answer:
        if not pending:
            print("\n  Nothing is waiting on you.")
            return 0

        choice = DecisionChoice(args.answer)
        first = store.get_decision(pending[0].decision_id)
        assert first is not None
        run = build_run(household, store, session_id=session_id, run_id=first.run_id)

        payload = build_resume_payload(
            [
                (
                    card,
                    DecisionResponse(
                        decision_id=card.decision_id,
                        choice=choice,
                        responded_at=datetime.now(UTC),
                    ),
                )
                for card in pending
            ]
        )
        print(f"\n  Answering {len(payload)} decision(s) with '{choice.value}' ...")
        result = run(payload)

        cards = persist_decisions(result, store, session_id=session_id) if was_interrupted(result) else []
        outcome = harvest(result, run, pending_decision_ids=[card.decision_id for card in cards])

        if cards:
            _print_cards(cards)
        else:
            print("  Run completed.")

        _print_activity(store, household, run.run_id)
        _print_brief(outcome.brief)
        _save_run(store, run, session_id=session_id, result=result, stats=_summarise(run))

        new_rules = store.list_policies(household)
        if len(new_rules) > len(policies):
            print("\n  New rule learned - Quiet Hours will stop asking about this:")
            for policy in new_rules[len(policies) :]:
                print(f"    - {policy.description}")
        return 0

    # ---- fresh run -------------------------------------------------------
    if pending:
        print(f"\n  {len(pending)} decision(s) already waiting. Answer them first:")
        _print_cards(pending)
        return 0

    run_id = new_id("run")
    shutil.rmtree(session_root() / f"session_{session_id}", ignore_errors=True)

    run = build_run(household, store, session_id=session_id, run_id=run_id)

    store.save_run(
        Run(
            run_id=run_id,
            household_id=household,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.RUNNING,
            session_id=session_id,
            started_at=utcnow(),
        )
    )

    result = run("Do this household's admin for today.")
    cards = persist_decisions(result, store, session_id=session_id) if was_interrupted(result) else []
    outcome = harvest(result, run, pending_decision_ids=[card.decision_id for card in cards])

    stats = _summarise(run)
    _save_run(store, run, session_id=session_id, result=result, stats=stats)

    _print_findings(outcome.findings)
    _print_activity(store, household, run_id)

    if cards:
        _print_cards(cards)
        print(
            f"\n  Run suspended. {stats.actions_autonomous}/{stats.actions_proposed} handled silently."
        )
    else:
        _print_brief(outcome.brief)
        print("\n  Nothing needs you today.")
        print(f"  {stats.actions_autonomous}/{stats.actions_proposed} actions handled silently.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
