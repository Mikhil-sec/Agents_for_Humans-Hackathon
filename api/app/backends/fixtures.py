"""The fixtures backend — static, contract-shaped JSON from `/fixtures`.

This is the reason Lane B never waits for Lane A, and it is what a judge gets from
`make demo`. It must always work with zero credentials.

**It is a stub of the store, not of the product.** Answering a card really does
move it out of the inbox, really does create the policy the button previewed, and
really does write an activity row — held in memory for the life of the process.
A demo where the buttons do nothing is worse than no demo.

`/fixtures` is Lane C's directory and is **read-only from here.** Every mutation
lives in this process and is lost on restart, which is the correct blast radius
for a mock.

Everything loaded here is parsed through the frozen contract models, so a fixture
that has drifted from `/contracts` fails at load with a pydantic error naming the
field — rather than at render time in front of a judge.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from quiet_hours_contracts import (
    ActivityEntry,
    DailyBrief,
    DecisionCard,
    DecisionChoice,
    DecisionResponse,
    DecisionStatus,
    Household,
    Money,
    Policy,
    PolicyScope,
    Run,
    RunStatus,
    RunTrigger,
)

from ..config import FIXTURES_DIR

M = TypeVar("M", bound=BaseModel)

SEED_HINT = (
    "Run `make fixtures` from the repo root. Lane C's seeder writes these; until it "
    "lands, Lane A's exporter does (see docs/status/DECISIONS.md, 2026-08-24)."
)

EM_DASH = "—"


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def _read(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"missing fixture {path.name} in {path.parent}. {SEED_HINT}")
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_list(path: Path, model: type[M]) -> list[M]:
    raw = _read(path)
    if not isinstance(raw, list):
        raise TypeError(f"{path.name} should hold a JSON array of {model.__name__}")
    try:
        return [model.model_validate(item) for item in raw]
    except ValidationError as exc:
        raise ValueError(f"{path.name} does not match the frozen contract:\n{exc}") from exc


def _parse_one(path: Path, model: type[M]) -> M:
    try:
        return model.model_validate(_read(path))
    except ValidationError as exc:
        raise ValueError(f"{path.name} does not match the frozen contract:\n{exc}") from exc


class FixturesBackend:
    """Contract models loaded from `/fixtures`, mutated in memory."""

    name = "fixtures"

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._dir = Path(fixtures_dir or FIXTURES_DIR)
        self._lock = threading.RLock()
        self._loaded = False

    # -- loading ------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load lazily so an empty `/fixtures` fails on the first request with a
        503 the web app can render, rather than crashing the process at import."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._household = _parse_one(self._dir / "household.json", Household)
            self._decisions = _parse_list(self._dir / "decisions.json", DecisionCard)
            self._runs = _parse_list(self._dir / "runs.json", Run)
            self._activity = _parse_list(self._dir / "activity.json", ActivityEntry)
            self._policies = _parse_list(self._dir / "policies.json", Policy)
            self._brief: DailyBrief | None = None
            brief_path = self._dir / "daily_brief.json"
            if brief_path.exists():
                self._brief = _parse_one(brief_path, DailyBrief)
            self._loaded = True

    # -- household ----------------------------------------------------------

    def household(self) -> Household:
        self._ensure_loaded()
        return self._household

    # -- decisions ----------------------------------------------------------

    def list_decisions(self, *, status: str | None = None) -> list[DecisionCard]:
        self._ensure_loaded()
        cards = self._expire_stale()
        if status:
            cards = [c for c in cards if c.status.value == status]
        return sorted(cards, key=lambda c: c.created_at, reverse=True)

    def get_decision(self, decision_id: str) -> DecisionCard | None:
        self._ensure_loaded()
        self._expire_stale()
        return next((c for c in self._decisions if c.decision_id == decision_id), None)

    def _expire_stale(self) -> list[DecisionCard]:
        """A pending card past its deadline is `expired`, not `pending`.

        The agent does this on its next run; in fixtures nothing else would, and
        `/` must never offer a button for an opportunity that has already gone.
        """
        now = _now()
        with self._lock:
            for card in self._decisions:
                if (
                    card.status is DecisionStatus.PENDING
                    and card.urgency_deadline is not None
                    and card.urgency_deadline <= now
                ):
                    card.status = DecisionStatus.EXPIRED
            return list(self._decisions)

    def respond(self, card: DecisionCard, response: DecisionResponse) -> tuple[str, str]:
        """Resolve the card, learn any policy it promised, and log the answer.

        In `live` this hands `interrupt_id` back to Strands. Here the run simply
        moves on — but the *observable* consequences are identical, which is what
        the web app is built against.
        """
        self._ensure_loaded()
        with self._lock:
            snoozed = response.choice is DecisionChoice.SNOOZE
            card.status = DecisionStatus.PENDING if snoozed else DecisionStatus.RESOLVED
            card.resolved_at = None if snoozed else response.responded_at
            if snoozed and response.snooze_until is not None:
                card.urgency_deadline = response.snooze_until

            policy = self._learn_policy(card, response)
            self._activity.append(self._entry_for(card, response, policy))

            run = next((r for r in self._runs if r.run_id == card.run_id), None)
            still_open = any(
                c.status is DecisionStatus.PENDING and c.run_id == card.run_id
                for c in self._decisions
            )
            status = RunStatus.WAITING_ON_USER if still_open else RunStatus.COMPLETED
            if run is not None:
                run.status = status
                run.finished_at = None if still_open else _now()
                if policy is not None:
                    run.stats.policies_applied += 1
            self._brief = self._brief  # headline is recomputed on read
            return card.run_id, status.value

    def _learn_policy(self, card: DecisionCard, response: DecisionResponse) -> Policy | None:
        """Create the rule the button previewed — and only that rule.

        The description is `creates_policy_preview` **verbatim**: the user agreed
        to those exact words, so the policies page must not show them different
        ones. Autonomy is never granted invisibly, and never granted wider than
        what was written on the button.
        """
        if response.choice not in (DecisionChoice.APPROVE_ALWAYS, DecisionChoice.DENY_ALWAYS):
            return None
        option = next((o for o in card.options if o.choice is response.choice), None)
        preview = option.creates_policy_preview if option else None
        if not preview:
            return None
        merchant = self._merchant_of(card)
        policy = Policy(
            policy_id=_new_id("pol"),
            household_id=card.household_id,
            scope=PolicyScope.MERCHANT if merchant else PolicyScope.GLOBAL,
            merchant=merchant,
            max_amount=card.amount,
            effect=(
                "auto_approve" if response.choice is DecisionChoice.APPROVE_ALWAYS else "auto_deny"
            ),
            description=preview[:200],
            created_from_decision_id=card.decision_id,
            created_at=response.responded_at,
        )
        self._policies.append(policy)
        return policy

    @staticmethod
    def _merchant_of(card: DecisionCard) -> str | None:
        """The headline reads `Cancel subscription — PhotoCloud`. `DecisionCard`
        carries no merchant field, so an em-dash split is the best available here;
        the live backend reads the real merchant off the proposed action."""
        if EM_DASH in card.headline:
            return card.headline.split(EM_DASH)[-1].strip() or None
        return None

    def _entry_for(
        self, card: DecisionCard, response: DecisionResponse, policy: Policy | None
    ) -> ActivityEntry:
        verb = {
            DecisionChoice.APPROVE: "Approved",
            DecisionChoice.APPROVE_ALWAYS: "Approved, and set a rule",
            DecisionChoice.EDIT: "Approved with edits",
            DecisionChoice.DENY: "Declined",
            DecisionChoice.DENY_ALWAYS: "Declined, and set a rule",
            DecisionChoice.SNOOZE: "Snoozed",
        }.get(response.choice, "Answered")
        return ActivityEntry(
            entry_id=_new_id("ent"),
            household_id=card.household_id,
            run_id=card.run_id,
            action_id=card.action_id,
            decision_id=card.decision_id,
            occurred_at=response.responded_at,
            summary=f"{verb} {EM_DASH} {card.headline}"[:160],
            rationale=response.note or card.why_asking,
            risk="confirm",
            was_autonomous=False,
            policy_id=policy.policy_id if policy else None,
            succeeded=True,
            impact=card.estimated_impact,
        )

    # -- runs ---------------------------------------------------------------

    def list_runs(self) -> list[Run]:
        self._ensure_loaded()
        return sorted(self._runs, key=lambda r: r.started_at, reverse=True)

    def get_run(self, run_id: str) -> Run | None:
        self._ensure_loaded()
        return next((r for r in self._runs if r.run_id == run_id), None)

    def trigger_run(self) -> Run:
        """The demo button. A fixtures run completes immediately and finds
        nothing new — the interesting state is already in the fixtures."""
        self._ensure_loaded()
        with self._lock:
            started = _now()
            run = Run(
                run_id=_new_id("run"),
                household_id=self._household.household_id,
                trigger=RunTrigger.MANUAL,
                status=RunStatus.COMPLETED,
                session_id=f"qh-{self._household.household_id}-{_new_id('sess')}",
                started_at=started,
                finished_at=started,
            )
            self._runs.append(run)
            return run

    # -- activity -----------------------------------------------------------

    def list_activity(self, *, autonomous: bool | None = None) -> list[ActivityEntry]:
        self._ensure_loaded()
        entries = self._activity
        if autonomous is not None:
            entries = [e for e in entries if e.was_autonomous is autonomous]
        return sorted(entries, key=lambda e: e.occurred_at, reverse=True)

    # -- policies -----------------------------------------------------------

    def list_policies(self, *, include_revoked: bool = False) -> list[Policy]:
        self._ensure_loaded()
        policies = self._policies if include_revoked else [p for p in self._policies if p.is_active]
        return sorted(policies, key=lambda p: p.created_at, reverse=True)

    def get_policy(self, policy_id: str) -> Policy | None:
        self._ensure_loaded()
        return next((p for p in self._policies if p.policy_id == policy_id), None)

    def revoke_policy(self, policy_id: str) -> Policy | None:
        self._ensure_loaded()
        with self._lock:
            policy = self.get_policy(policy_id)
            if policy is None:
                return None
            if policy.revoked_at is None:
                policy.revoked_at = _now()
            return policy

    # -- brief --------------------------------------------------------------

    def latest_brief(self) -> DailyBrief | None:
        """The fixture brief is a snapshot of the run that produced it.

        Its *counts* go stale the moment the user answers something, so they are
        recomputed from current state. The shape is untouched, and in `live` the
        agent recomputes exactly these fields on its next run — so the web app
        sees the same thing either way.
        """
        self._ensure_loaded()
        base = self._brief
        if base is None:
            if not self._activity and not self._runs:
                return None
            base = DailyBrief(
                brief_id=_new_id("brf"),
                household_id=self._household.household_id,
                run_id=self._runs[0].run_id if self._runs else "",
                generated_at=_now(),
                headline="Nothing needs you today",
            )
        pending = [c.decision_id for c in self.list_decisions(status="pending")]
        silent = [e.summary for e in self.list_activity(autonomous=True)]
        total = len(self._activity)
        return base.model_copy(
            update={
                "pending_decision_ids": pending,
                "handled_silently": silent[:12],
                "headline": self._headline(len(pending)),
                "autonomy_rate": (len(silent) / total) if total else 1.0,
            }
        )

    @staticmethod
    def _headline(pending: int) -> str:
        if pending == 0:
            return "Nothing needs you today"
        if pending == 1:
            return "One thing needs you today"
        return f"{pending} things need you today"

    # -- derived ------------------------------------------------------------

    def savings_this_month(self) -> Money | None:
        self._ensure_loaded()
        brief = self.latest_brief()
        return brief.savings_this_month if brief else None
