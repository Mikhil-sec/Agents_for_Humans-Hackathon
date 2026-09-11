"""The policy gate — a Strands hook that governs every tool call.

This is the heart of Quiet Hours. Registering on `BeforeToolCallEvent` means
*every* tool call passes through the gate, including ones the model improvises.
Safety is not something the prompt asks for politely; it is structural.

    low risk, or covered by a rule you granted  -> execute, log it, stay quiet
    anything else                               -> event.interrupt() -> DecisionCard

Verified against `strands-agents` 1.53.0 by the A1 spike
(`agent/spikes/a1_interrupt/`). Read its README before changing anything here.
Three findings from A1 shape this file:

1. **`event.interrupt()` does not kill the process.** It raises
   `InterruptException`; the event loop catches it, persists the session, and
   returns an `AgentResult` normally. So the *runner* reliably gets control back
   and is the right place to write the card — it is the only party that knows the
   authoritative `interrupt_id`. See `card_from_interrupt` below.
2. **The gate body runs twice** — once raising, once returning the answer on
   resume, in a different process. Everything here must be idempotent.
3. The `reason` passed to `interrupt()` is persisted in the session and handed
   back verbatim, so it must stay JSON-serialisable.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from quiet_hours_contracts import (
    DEFAULT_RISK_BY_ACTION,
    RISK_ORDER,
    ActionKind,
    DecisionCard,
    DecisionChoice,
    DecisionOption,
    DecisionResponse,
    DecisionStatus,
    Evidence,
    Finding,
    Money,
    Policy,
    PolicyScope,
    ProposedAction,
    RiskTier,
)
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from .policy import Verdict, effective_risk, evaluate, policy_from_decision
from .store import Store, build_activity_entry, new_id, utcnow

logger = logging.getLogger(__name__)

INTERRUPT_NAME = "qh-approval"
"""Stable interrupt name. Stored on every DecisionCard and echoed back on resume.
Do not change it without a migration — suspended sessions in S3 reference it."""

TOOL_ACTION_KINDS: dict[str, ActionKind] = {kind.value: kind for kind in ActionKind}
"""Governed tools, by convention: a tool named exactly like an `ActionKind` value
is that kind of action. Anything else is an ungoverned read and passes straight
through. The convention means a new action kind cannot be added without its tool
becoming governed automatically — the safe direction to fail in."""

APPROVING_CHOICES = frozenset(
    {DecisionChoice.APPROVE, DecisionChoice.APPROVE_ALWAYS, DecisionChoice.EDIT}
)
"""Everything else — including anything unrecognised — means no. Fail closed."""


def decision_id_for(tool_use_id: str) -> str:
    """Deterministic decision id for a tool call.

    Must be stable across processes: the gate runs once before the interrupt and
    again on resume, and both passes have to agree on which card this is. Derived
    rather than random for exactly that reason. Still opaque — nothing may parse it.
    """
    return f"dec_{uuid.uuid5(uuid.NAMESPACE_OID, tool_use_id).hex[:24]}"


@dataclass
class _GateRecord:
    """What the gate decided, kept so the after-hook can write the audit line."""

    action: ProposedAction
    verdict: Verdict
    decision_id: str | None = None
    choice: DecisionChoice | None = None


class PolicyHook(HookProvider):
    """Registers the policy gate and the audit trail on tool calls.

    The gate decides; `policy.evaluate` is the only thing that decides *what*.
    This class contains no risk logic of its own — that separation is the point,
    and it is why the policy engine can stay a pure, testable function.
    """

    def __init__(
        self,
        household_id: str,
        policies: list[Policy],
        store: Store,
        *,
        run_id: str,
        interrupt_name: str = INTERRUPT_NAME,
    ) -> None:
        self.household_id = household_id
        self.policies = policies
        self.store = store
        self.run_id = run_id
        self.interrupt_name = interrupt_name

        self._verdicts: dict[str, tuple[ProposedAction, Verdict]] = {}
        """Recorded for the run's stats and the autonomy chart, keyed by
        `toolUseId` so one tool call counts once.

        **The gate runs twice for every action that interrupts** — once to raise
        the interrupt and once, on resume, to collect the answer (A1). A plain
        list therefore counted every interrupted action twice, which deflated the
        autonomy rate: the denominator grew by one for each thing the user was
        asked about, and asking is precisely what the metric is supposed to
        penalise. The headline number was wrong in the pessimistic direction,
        which is why it survived so long unnoticed.

        Keyed by `toolUseId`, which is stable across the process boundary because
        it is persisted in the session — the same property `decision_id_for`
        relies on. The later verdict wins: it is the one that decided the
        outcome."""

        self.new_policies: list[Policy] = []
        """Policies created by APPROVE_ALWAYS / DENY_ALWAYS answers this run."""

        self._pending: dict[str, _GateRecord] = {}

        self._executed: dict[str, ProposedAction] = {}
        """Actions whose tool call actually ran and succeeded, keyed by
        `toolUseId` for the same reason `_verdicts` is.

        **Not the same set as the silently-allowed ones.** An action the user was
        asked about and approved executes too — that is what approving means —
        and it is the only set `RunStats.estimated_annual_savings` can honestly
        be counted from. Filtering on `Verdict.allow_silently` instead would
        report zero savings for a household that approved every cancellation it
        was asked about, which is the opposite of what happened."""

    @property
    def verdicts(self) -> list[tuple[ProposedAction, Verdict]]:
        """One entry per governed tool call, in the order first seen."""
        return list(self._verdicts.values())

    @property
    def executed(self) -> list[ProposedAction]:
        """The actions this run actually carried out, silently or on approval."""
        return list(self._executed.values())

    # -- registration ------------------------------------------------------

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.gate)
        registry.add_callback(AfterToolCallEvent, self.audit)

    # -- the gate ----------------------------------------------------------

    def gate(self, event: BeforeToolCallEvent) -> None:
        """Allow, interrupt, or cancel one tool call."""
        action = self._action_from_tool_use(event.tool_use, event.invocation_state)
        if action is None:
            return  # not a governed tool; let it through

        category = self._category_of(action)
        verdict = evaluate(action, self.policies, category=category)

        tool_use_id = event.tool_use["toolUseId"]
        first_pass = tool_use_id not in self._verdicts
        self._verdicts[tool_use_id] = (action, verdict)
        record = _GateRecord(action=action, verdict=verdict)
        self._pending[tool_use_id] = record

        if verdict.allow_silently:
            # Executes without asking. The audit line is written in `audit()`,
            # once we know whether it actually worked.
            if first_pass and verdict.policy_id:
                self._count_policy_use(verdict.policy_id)
            return

        decision_id = decision_id_for(tool_use_id)
        record.decision_id = decision_id
        self.store.put_action(action)

        # First pass: raises InterruptException and unwinds. Second pass (on
        # resume, possibly days later in another process): returns the answer.
        answer = event.interrupt(
            self.interrupt_name,
            reason=self._card_payload(action, verdict, decision_id, category),
        )

        response = self._parse_response(answer, decision_id)
        record.choice = response.choice if response else None

        if response is not None:
            self.store.resolve_decision(response.decision_id, response)
            self._maybe_learn_policy(action, response, category)

        if response is None or response.choice not in APPROVING_CHOICES:
            event.cancel_tool = self._decline_message(response)

    # -- the audit trail ---------------------------------------------------

    def audit(self, event: AfterToolCallEvent) -> None:
        """Write the `ActivityEntry` for a governed tool call.

        Every action produces one — autonomous or not, success or failure. Done
        here rather than in the gate because only here do we know the outcome.
        """
        record = self._pending.pop(event.tool_use["toolUseId"], None)
        if record is None:
            return

        cancelled = event.cancel_message is not None
        succeeded = event.exception is None and not cancelled

        if cancelled:
            error = str(event.cancel_message)
        elif event.exception is not None:
            error = f"{type(event.exception).__name__}: {event.exception}"
        else:
            error = None

        if succeeded:
            self._executed[event.tool_use["toolUseId"]] = record.action

        entry = build_activity_entry(
            record.action,
            risk=record.verdict.effective_risk,
            was_autonomous=record.verdict.allow_silently,
            succeeded=succeeded,
            rationale=record.verdict.reason,
            policy_id=record.verdict.policy_id,
            decision_id=record.decision_id,
            error=error,
        )
        self.store.write_activity(entry)

    # -- helpers -----------------------------------------------------------

    def _action_from_tool_use(
        self, tool_use: dict[str, Any], invocation_state: dict[str, Any] | None = None
    ) -> ProposedAction | None:
        """Map a tool call to a governed action, or None if it needs no gate."""
        kind = TOOL_ACTION_KINDS.get(tool_use.get("name", ""))
        if kind is None:
            return None

        tool_input = tool_use.get("input") or {}
        state = invocation_state or {}
        household_id = state.get("household_id") or self.household_id
        run_id = state.get("run_id") or self.run_id
        finding = self._finding_for(tool_input, state)

        # The graph (A5) writes a ProposedAction and passes its id to the tool.
        action_id = tool_input.get("action_id")
        if isinstance(action_id, str):
            stored = self.store.get_action(action_id)
            if stored is not None:
                return stored
            logger.warning("tool cited unknown action_id=%s; synthesising", action_id)

        # No backing action: the model improvised this call. It still passes
        # through the gate at the floor risk for its kind — which is the whole
        # safety table. Deliberately *not* inflated to CONFIRM: that would make
        # the agent ask permission to file a record, and the product's entire
        # claim is that routine work happens silently.
        floor = DEFAULT_RISK_BY_ACTION[kind]

        # A5: the graph's specialists pass their own `rationale` on the tool call,
        # because it is what the user reads on the card. Only the *wording* comes
        # from the model — `risk` stays pinned to the floor below, so a persuasive
        # rationale still cannot buy an action a quieter tier.
        stated = tool_input.get("rationale")
        rationale = (
            stated.strip()
            if isinstance(stated, str) and stated.strip()
            else (
                "The agent proposed this directly, without a recorded finding. "
                "Quiet Hours still applies the same policy gate."
            )
        )

        # The finding is what makes the card answerable: its evidence is the
        # quoted line from the household's own inbox that the user reads under
        # "why am I being asked this", and its category is what a
        # `CATEGORY`-scoped policy is learned against. Without one, both fall
        # back to a description of the tool call, which explains nothing.
        params = dict(tool_input)
        if finding is not None and finding.category and "category" not in params:
            params["category"] = finding.category

        return ProposedAction(
            action_id=action_id if isinstance(action_id, str) else new_id("act"),
            household_id=household_id,
            run_id=run_id,
            finding_id=finding.finding_id if finding is not None else "unbacked",
            kind=kind,
            risk=floor,
            summary=self._summarise(kind, tool_input),
            rationale=rationale,
            params=params,
            reversible=RISK_ORDER[floor] <= RISK_ORDER[RiskTier.NOTIFY],
            estimated_impact=self._money_from(tool_input),
            evidence=self._evidence_for(finding, tool_use, tool_input),
            created_at=utcnow(),
        )

    def _count_policy_use(self, policy_id: str) -> None:
        """Record that a rule spared the user a question.

        `Policy.times_applied` has been declared in `/contracts` since the freeze
        and **incremented nowhere**, so the policies page reported "not used yet"
        against every rule the household had ever granted — including rules that
        were, at that moment, the reason the run stayed quiet. That is the one
        page whose entire job is to justify the autonomy the user handed over.

        Guarded by `first_pass` at the call site for the same reason `_verdicts`
        is keyed by `toolUseId`: the gate body runs again for a replayed node,
        and a rule that silenced one action must not be counted twice for it.
        """
        for policy in self.policies:
            if policy.policy_id != policy_id:
                continue
            policy.times_applied += 1
            self.store.save_policy(policy)
            return
        logger.warning("verdict cited unknown policy_id=%s; not counted", policy_id)

    # -- backing a tool call with the finding it came from ------------------

    #: Free-text tool fields a merchant name can be mentioned inside. The
    #: scheduling tools take no `merchant` — a reminder has a subject, a calendar
    #: entry a title — but they still name the merchant in it, which is what
    #: makes them resolvable at all.
    _TEXT_FIELDS = ("merchant", "subject", "title", "recipient", "note")

    def _finding_for(self, tool_input: dict[str, Any], state: dict[str, Any]) -> Finding | None:
        """Which of this run's findings this tool call is acting on.

        **Resolved here rather than asked of the model.** `graph.FindingRecorder`
        promotes triage's drafts into contract `Finding`s before any specialist
        runs and puts them in `invocation_state`, so by the time a tool call
        reaches the gate the finding it came from already exists with a real id.
        Matching it is code's job: a model that could name its own backing
        evidence could also name someone else's.

        Order:

        1. An explicit `finding_id` on the call. No tool declares that parameter
           today, so nothing can supply it — the branch is here because the id
           now exists to be cited, and this is where a citation would be honoured.
        2. The merchant. Exactly on the `merchant` argument, then mentioned
           inside one of the other free-text fields.

        Returns None when nothing matches, which is not an error: an improvised
        tool call is legitimate and still passes the gate at its floor risk. It
        just cannot claim evidence it does not have.
        """
        findings = [f for f in (state.get("findings") or []) if isinstance(f, Finding)]
        if not findings:
            return None

        cited = tool_input.get("finding_id")
        if isinstance(cited, str) and cited:
            for finding in findings:
                if finding.finding_id == cited:
                    return finding
            logger.warning("tool cited unknown finding_id=%s; matching on merchant", cited)

        text = " ".join(
            value.casefold()
            for field in self._TEXT_FIELDS
            if isinstance(value := tool_input.get(field), str) and value.strip()
        )
        if not text:
            return None

        named = tool_input.get("merchant")
        named = named.strip().casefold() if isinstance(named, str) else ""

        matches = [
            finding
            for finding in findings
            if finding.merchant
            and (finding.merchant.casefold() == named or finding.merchant.casefold() in text)
        ]
        if not matches:
            return None
        if len(matches) > 1:
            # One merchant, two findings in a single run — a bill *and* a price
            # rise, say. Confidence is the only ordering triage gives us, and
            # picking silently would hide a real ambiguity from whoever reads
            # the trail.
            matches.sort(key=lambda finding: finding.confidence, reverse=True)
            logger.warning(
                "%d findings match this call; backing it with the most confident (%s)",
                len(matches),
                matches[0].finding_id,
            )
        return matches[0]

    @staticmethod
    def _evidence_for(
        finding: Finding | None, tool_use: dict[str, Any], tool_input: dict[str, Any]
    ) -> list[Evidence]:
        """The finding's own evidence, or an honest description of the call.

        The fallback deliberately still says `unbacked` rather than inventing a
        `signal_id`. A card that cites nothing is a card the activity trail can
        be audited against; a card citing a signal that does not exist is worse
        than one citing none.
        """
        if finding is not None and finding.evidence:
            return list(finding.evidence)
        return [
            Evidence(
                signal_id="unbacked",
                excerpt=f"Tool call {tool_use.get('name')} with {sorted(tool_input)}"[:500],
            )
        ]

    @staticmethod
    def _summarise(kind: ActionKind, tool_input: dict[str, Any]) -> str:
        """One line for the activity trail and the top of the decision card.

        Not every action has a merchant — a reminder has a subject, a calendar
        entry has a title. Falling back through them keeps the trail readable
        instead of listing three identical "Set reminder" rows.
        """
        label = kind.value.replace("_", " ").capitalize()
        for key in ("merchant", "subject", "title", "recipient"):
            subject = tool_input.get(key)
            if isinstance(subject, str) and subject.strip():
                return f"{label} — {subject.strip()}"[:160]
        return label[:160]

    @staticmethod
    def _money_from(tool_input: dict[str, Any]) -> Money | None:
        amount = tool_input.get("amount_minor") or tool_input.get("monthly_amount_minor")
        if not isinstance(amount, int) or isinstance(amount, bool):
            return None
        currency = tool_input.get("currency")
        return Money(
            amount_minor=amount,
            currency=currency if isinstance(currency, str) and len(currency) == 3 else "GBP",
        )

    @staticmethod
    def _category_of(action: ProposedAction) -> str | None:
        category = action.params.get("category")
        return category if isinstance(category, str) else None

    def _card_payload(
        self,
        action: ProposedAction,
        verdict: Verdict,
        decision_id: str,
        category: str | None,
    ) -> dict[str, Any]:
        """The `reason` handed to `interrupt()`.

        Persisted in the session and returned verbatim in `result.interrupts[]`,
        so it must be JSON-serialisable. `card_from_interrupt` turns it back into
        a `DecisionCard` once the runner knows the interrupt id.
        """
        return {
            "decision_id": decision_id,
            "household_id": action.household_id,
            "run_id": action.run_id,
            "action_id": action.action_id,
            "headline": action.summary[:120],
            "body": action.rationale,
            "why_asking": verdict.reason[:240],
            "amount": action.estimated_impact.model_dump(mode="json")
            if action.estimated_impact
            else None,
            "estimated_impact": action.estimated_impact.model_dump(mode="json")
            if action.estimated_impact
            else None,
            "evidence": [item.model_dump(mode="json") for item in action.evidence],
            "options": [
                option.model_dump(mode="json")
                for option in self._options_for(action, verdict, category)
            ],
        }

    def _options_for(
        self, action: ProposedAction, verdict: Verdict, category: str | None
    ) -> list[DecisionOption]:
        """The buttons on the card.

        `APPROVE_ALWAYS` is deliberately withheld for `NEVER_AUTO` actions. The
        policy engine rejects those before it ever reads a policy, so offering to
        create one would be a lie to the user about what the rule would do.
        """
        options = [
            DecisionOption(choice=DecisionChoice.APPROVE, label="Do it", is_default=True),
        ]

        if verdict.effective_risk is not RiskTier.NEVER_AUTO:
            preview = policy_from_decision(
                action,
                policy_id="preview",
                household_id=action.household_id,
                decision_id="preview",
                approve=True,
                scope=PolicyScope.MERCHANT
                if action.params.get("merchant")
                else PolicyScope.ACTION_KIND,
                category=category,
            ).description
            options.append(
                DecisionOption(
                    choice=DecisionChoice.APPROVE_ALWAYS,
                    label="Always do this",
                    description="Creates a rule so Quiet Hours stops asking.",
                    creates_policy_preview=preview,
                )
            )

        options.append(DecisionOption(choice=DecisionChoice.DENY, label="No, skip it"))
        return options

    def _parse_response(self, answer: Any, fallback_decision_id: str) -> DecisionResponse | None:
        """Read the user's answer. Anything unparseable means no.

        Fail closed: an ambiguous answer must never be read as consent to spend
        money, send a message, or cancel a service.
        """
        if isinstance(answer, DecisionResponse):
            return answer

        if isinstance(answer, str):
            # Bare-string answers are a convenience for CLI testing only.
            try:
                choice = DecisionChoice(answer.strip().casefold())
            except ValueError:
                logger.warning("unrecognised answer %r; treating as a denial", answer)
                return None
            return DecisionResponse(
                decision_id=fallback_decision_id, choice=choice, responded_at=utcnow()
            )

        if isinstance(answer, dict):
            payload = dict(answer)
            payload.setdefault("decision_id", fallback_decision_id)
            payload.setdefault("responded_at", utcnow())
            try:
                return DecisionResponse.model_validate(payload)
            except Exception as exc:  # noqa: BLE001 - any invalid answer is a denial
                logger.warning("invalid DecisionResponse (%s); treating as a denial", exc)
                return None

        logger.warning("answer of type %s; treating as a denial", type(answer).__name__)
        return None

    @staticmethod
    def _decline_message(response: DecisionResponse | None) -> str:
        if response is None:
            return "Quiet Hours could not read the answer, so it did nothing."
        if response.choice is DecisionChoice.SNOOZE:
            return "The user snoozed this decision."
        return "The user declined this action."

    def _maybe_learn_policy(
        self, action: ProposedAction, response: DecisionResponse, category: str | None
    ) -> None:
        """Turn an ALWAYS answer into a rule. This is how the interrupt rate falls.

        Guarded twice over: no policy is created for a `NEVER_AUTO` action, and
        even if one were, `policy.evaluate` rejects `NEVER_AUTO` before it reads
        any policy. Belt and braces, on the rule that matters most.
        """
        if response.choice not in (DecisionChoice.APPROVE_ALWAYS, DecisionChoice.DENY_ALWAYS):
            return

        approve = response.choice is DecisionChoice.APPROVE_ALWAYS
        if approve and effective_risk(action) is RiskTier.NEVER_AUTO:
            logger.warning(
                "refusing to create an auto-approve policy for NEVER_AUTO action %s",
                action.action_id,
            )
            return

        policy = policy_from_decision(
            action,
            policy_id=new_id("pol"),
            household_id=action.household_id,
            decision_id=response.decision_id,
            approve=approve,
            scope=PolicyScope.MERCHANT
            if action.params.get("merchant")
            else PolicyScope.ACTION_KIND,
            category=category,
            # **When the user answered, not when this code ran.** The replay
            # simulates four weeks in seconds, so wall clock stamps every rule
            # with today and the policies page reads "since 10 Sept" for a rule
            # learned in the first week. It is the right semantics in production
            # too: a rule comes into force when it is granted, and a run resumed
            # days after it suspended is answered on the day of the answer.
            now=response.responded_at,
        )
        self.store.save_policy(policy)
        self.new_policies.append(policy)
        self.policies.append(policy)


def card_from_interrupt(interrupt: Any, *, session_id: str) -> DecisionCard | None:
    """Assemble the persistable `DecisionCard` from a raised interrupt.

    Called by the runner, not the hook — per A1, the runner is the only party
    that knows the authoritative `interrupt_id`, and `interrupt()` returns
    control to it cleanly rather than killing the process.
    """
    payload = getattr(interrupt, "reason", None)
    if not isinstance(payload, dict):
        logger.warning("interrupt %s carried no card payload", getattr(interrupt, "id", "?"))
        return None

    amount = payload.get("amount")
    impact = payload.get("estimated_impact")

    return DecisionCard(
        decision_id=payload["decision_id"],
        household_id=payload["household_id"],
        run_id=payload["run_id"],
        action_id=payload["action_id"],
        session_id=session_id,
        interrupt_id=interrupt.id,
        interrupt_name=interrupt.name,
        headline=payload["headline"],
        body=payload["body"],
        why_asking=payload["why_asking"],
        options=[DecisionOption.model_validate(option) for option in payload["options"]],
        amount=Money.model_validate(amount) if amount else None,
        estimated_impact=Money.model_validate(impact) if impact else None,
        evidence=[Evidence.model_validate(item) for item in payload["evidence"]],
        status=DecisionStatus.PENDING,
        created_at=datetime.now(UTC),
    )
