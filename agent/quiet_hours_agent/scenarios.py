"""Scenarios — a day's world and the mock reasoning about it, as one object.

`mock_reasoning.py` holds *the* demo day: four signals, three actions, one
interrupt. That is deliberately fixed, because it is the thing a judge sees.

A6 needs four different days, each reasoning over different signals, so that the
policy engine has something new to be asked about each week and something
recurring to go quiet about. This module is the mechanism for that; `replay.py`
holds the four weeks' data.

## The shape, and why

    Item  =  one signal  ->  one finding  ->  N actions

Binding them together is what keeps the citations honest. Every `Finding` and
every `ProposedAction` must cite a real `signal_id` as evidence — an invented
citation is worse than no finding at all — and the surest way to guarantee that
is to make it impossible to write a finding that is not attached to a signal.

## What a scenario does *not* control

Whether an action runs silently or interrupts. That is `policy.py`'s decision,
every time, from the policies actually in the store. A scenario says "the
negotiator tries to cancel PhotoCloud for £4.99"; the policy engine says whether
the user gets asked. **The autonomy curve has to be measured, not authored**, and
this separation is what makes that true — see `replay.py`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from quiet_hours_contracts import FindingKind, Money, Signal, SignalKind

from .mock_reasoning import MockScript
from .models import ScriptedStep

logger = logging.getLogger(__name__)

CURRENCY = "GBP"

NODE_TOOLS: dict[str, str] = {
    "file_record": "bill_analyst",
    "tag_merchant": "bill_analyst",
    "update_budget_ledger": "bill_analyst",
    "pay_bill": "bill_analyst",
    "dispute_charge": "bill_analyst",
    "cancel_subscription": "negotiator",
    "downgrade_plan": "negotiator",
    "draft_email": "negotiator",
    "set_reminder": "scheduler",
    "add_calendar_event": "scheduler",
    "reschedule_appointment": "scheduler",
}
"""Which specialist owns each tool.

Mirrors `BILL_TOOLS` / `NEGOTIATION_TOOLS` / `SCHEDULING_TOOLS` in
`tools/__init__.py`. A scenario that routes a tool to the wrong node produces an
agent calling a tool it was never given, which fails at run time with a message
about an unknown tool rather than anything useful — so
`test_replay.py::test_every_scenario_action_is_routed_to_a_node_that_owns_it`
checks the two lists agree.
"""


@dataclass(frozen=True)
class Act:
    """One tool call a specialist will attempt."""

    tool: str
    params: dict[str, Any]
    summary: str
    rationale: str
    risk: str = "silent"
    """What the *agent* proposes. The floor in `DEFAULT_RISK_BY_ACTION` still
    applies — an agent may raise its own risk, never lower it — so this being
    wrong makes an action stricter, never laxer."""

    @property
    def node(self) -> str:
        return NODE_TOOLS[self.tool]


@dataclass(frozen=True)
class Item:
    """One signal, what the agent concluded from it, and what it wants to do."""

    signal_id: str
    kind: SignalKind
    source: str
    subject: str
    body: str
    finding_kind: FindingKind
    finding_title: str
    finding_detail: str
    actions: list[Act]
    merchant: str | None = None
    category: str | None = None
    amount_minor: int | None = None
    previous_amount_minor: int | None = None
    confidence: float = 0.9
    occurred_offset: timedelta = timedelta(hours=-6)

    @property
    def excerpt(self) -> str:
        """The evidence snippet. The signal's own words, never a paraphrase."""
        return self.body[:200]


@dataclass(frozen=True)
class Scenario:
    """A day's signals plus the mock script for every node that sees them."""

    key: str
    label: str
    items: list[Item]
    headline: str = "Here is your day."

    def signals(self, household_id: str, now: datetime) -> list[Signal]:
        return [
            Signal(
                signal_id=item.signal_id,
                household_id=household_id,
                kind=item.kind,
                occurred_at=now + item.occurred_offset,
                ingested_at=now,
                source=item.source,
                subject=item.subject,
                body=item.body,
                merchant=item.merchant,
                amount=(
                    Money(amount_minor=item.amount_minor, currency=CURRENCY)
                    if item.amount_minor is not None
                    else None
                ),
            )
            for item in self.items
        ]

    def scripts(self) -> dict[str, MockScript]:
        """The per-node scripts, built from the items."""
        return {
            "ingest": self._ingest_script(),
            "triage": self._triage_script(),
            **self._specialist_scripts(),
            "brief": self._brief_script(),
        }

    # -- per node ----------------------------------------------------------

    def _ingest_script(self) -> MockScript:
        """The ingest node's text is what triage reads, so it carries the ids.

        Triage is required to cite a `signal_id` on every finding. If the ids are
        hard to see in the text it is handed, the citation gets invented.
        """
        lines = [f"{len(self.items)} signal(s) arrived."]
        for item in self.items:
            money = (
                f" | {CURRENCY} {item.amount_minor / 100:.2f}"
                if item.amount_minor is not None
                else ""
            )
            merchant = f" | {item.merchant}" if item.merchant else ""
            lines.append(f"- [{item.signal_id}] {item.source}{merchant}{money} — {item.body}")
        return MockScript(steps=[ScriptedStep("load_signals", {})], final_text="\n".join(lines))

    def _triage_script(self) -> MockScript:
        findings = []
        for item in self.items:
            finding: dict[str, Any] = {
                "kind": item.finding_kind.value,
                "title": item.finding_title,
                "detail": item.finding_detail,
                "confidence": item.confidence,
                "evidence": [{"signal_id": item.signal_id, "excerpt": item.excerpt}],
            }
            if item.merchant:
                finding["merchant"] = item.merchant
            if item.category:
                finding["category"] = item.category
            if item.amount_minor is not None:
                finding["amount_minor"] = item.amount_minor
                finding["currency"] = CURRENCY
            if item.previous_amount_minor is not None:
                finding["previous_amount_minor"] = item.previous_amount_minor
            findings.append(finding)

        return MockScript(
            steps=[ScriptedStep("TriageResult", {"findings": findings})],
            final_text=f"{len(findings)} finding(s).",
        )

    def _specialist_scripts(self) -> dict[str, MockScript]:
        by_node: dict[str, list[tuple[Item, Act]]] = {}
        for item in self.items:
            for act in item.actions:
                by_node.setdefault(act.node, []).append((item, act))

        scripts: dict[str, MockScript] = {}
        for node, pairs in by_node.items():
            steps = [ScriptedStep(act.tool, dict(act.params)) for _item, act in pairs]

            # The structured-output step goes last: it is what `harvest()` reads
            # to build `ProposedAction`s, and it must describe calls that were
            # actually attempted rather than ones merely planned.
            steps.append(
                ScriptedStep(
                    "ActionPlan",
                    {
                        "actions": [
                            {
                                "kind": act.tool,
                                "summary": act.summary,
                                "rationale": act.rationale,
                                "risk": act.risk,
                                "merchant": item.merchant,
                                "reversible": act.risk in ("silent", "notify"),
                                "evidence": [
                                    {"signal_id": item.signal_id, "excerpt": item.excerpt}
                                ],
                            }
                            for item, act in pairs
                        ],
                        "note": "",
                    },
                )
            )
            scripts[node] = MockScript(steps=steps, final_text=f"{len(pairs)} action(s) attempted.")
        return scripts

    def _brief_script(self) -> MockScript:
        """The digest.

        `handled_silently` is left empty on purpose. `graph.py::_brief_from`
        measures the real numbers from the audit trail — a model writing its own
        summary of how autonomous it was is exactly the figure nobody should
        trust.
        """
        return MockScript(
            steps=[
                ScriptedStep(
                    "BriefDraft",
                    {"headline": self.headline, "handled_silently": [], "note": ""},
                )
            ],
            final_text="Brief ready.",
        )


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

REGISTRY: dict[str, Scenario] = {}
"""Scenarios by key.

Keyed by string rather than passed as an object because the key has to survive
`invocation_state`, which crosses into the `load_signals` tool. Registering is
`replay.py`'s job; nothing here knows what a week looks like.
"""

_scripts_cache: dict[str, dict[str, MockScript]] = {}


def register(scenario: Scenario) -> Scenario:
    REGISTRY[scenario.key] = scenario
    _scripts_cache.pop(scenario.key, None)
    return scenario


def get(key: str | None) -> Scenario | None:
    return REGISTRY.get(key) if key else None


def scripts_for(key: str | None) -> dict[str, MockScript] | None:
    """The node scripts for a scenario, built once and cached.

    Cached because `build_graph` is called once per run and the replay builds
    four weeks' worth; rebuilding the same dicts each time is pure waste, and the
    scenarios are frozen so the result cannot go stale.
    """
    scenario = get(key)
    if scenario is None:
        return None
    if key not in _scripts_cache:
        _scripts_cache[key] = scenario.scripts()  # type: ignore[index]
    return _scripts_cache[key]  # type: ignore[index]


def signals_for(key: str | None, household_id: str, now: datetime) -> list[Signal] | None:
    scenario = get(key)
    return scenario.signals(household_id, now) if scenario else None


@dataclass
class ScenarioStats:
    """What one scenario contains, for tests and for the replay's own header."""

    actions: int = 0
    by_tool: dict[str, int] = field(default_factory=dict)

    @classmethod
    def of(cls, scenario: Scenario) -> ScenarioStats:
        stats = cls()
        for item in scenario.items:
            for act in item.actions:
                stats.actions += 1
                stats.by_tool[act.tool] = stats.by_tool.get(act.tool, 0) + 1
        return stats
