"""Scripted reasoning for mock mode — one script per graph node.

**Mock mode must work with zero credentials.** That is how a hackathon judge runs
us (`git clone && make demo`) and it is a hard rule in the root `AGENTS.md`. So
every node needs something to say without Bedrock, and this is it.

These scripts are *not* test doubles. They are the mock-mode reasoning, and the
demo runs on them, so they are written to tell the product's story honestly:

* the gas bill is real work that happens **silently**;
* the dentist reminder is real work that happens **silently**;
* exactly one thing — cancelling an unused gym membership — **spends money and
  stops to ask**.

That ratio is the pitch. A script that interrupted twice would misrepresent the
product as much as one that never interrupted at all.

A step whose `tool_name` is a schema class name (`TriageResult`, `ActionPlan`,
`BriefDraft`) drives that node's `structured_output_model`: Strands injects the
structured-output tool under the model class's own name, so naming the step after
the class is all it takes.

When A4 lands real providers and a `BedrockModel` runs the graph for real, these
stay as the mock-mode path. They are deleted only if mock mode is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ScriptedStep

# The demo signal ids, from `signals.py`. Evidence must cite a real one — an
# invented citation is worse than no finding, so keep these in step.
SIG_GAS = "sig_gas_bill"
SIG_FITLIFE = "sig_fitlife_charge"
SIG_STREAMLY = "sig_streamly_trial"
SIG_DENTIST = "sig_dentist_appt"


@dataclass(frozen=True)
class MockScript:
    """What one node does, and what it says when it is done."""

    steps: list[ScriptedStep] = field(default_factory=list)
    final_text: str = "Done."


INGEST = MockScript(
    steps=[ScriptedStep("load_signals", {})],
    # The node's own text is what reaches triage, so it has to carry the signals
    # forward in full — including the ids, which triage is required to cite.
    final_text=(
        "Four signals arrived today.\n"
        f"- [{SIG_GAS}] mock_gmail | British Gas | GBP 84.20 — bill ready, due the 28th; "
        "last month was GBP 83.10.\n"
        f"- [{SIG_FITLIFE}] mock_bank | FitLife | GBP 38.00 — monthly gym charge; "
        "no visit recorded in 90 days.\n"
        f"- [{SIG_STREAMLY}] mock_gmail | Streamly | GBP 12.99 — free trial ends in 3 days, "
        "then charges monthly.\n"
        f"- [{SIG_DENTIST}] mock_calendar | Bridge Street Dental — check-up on the 2nd at "
        "09:15, practice asks for confirmation 48 hours ahead."
    ),
)

TRIAGE = MockScript(
    steps=[
        ScriptedStep(
            "TriageResult",
            {
                "findings": [
                    {
                        "kind": "bill_due",
                        "title": "British Gas bill due on the 28th",
                        "detail": (
                            "Your gas bill is GBP 84.20, due on the 28th. That is GBP 1.10 "
                            "more than last month, which is normal seasonal variation."
                        ),
                        "confidence": 0.95,
                        "merchant": "British Gas",
                        "category": "energy",
                        "amount_minor": 8420,
                        "previous_amount_minor": 8310,
                        "currency": "GBP",
                        "evidence": [
                            {
                                "signal_id": SIG_GAS,
                                "excerpt": (
                                    "Your bill for this month is GBP 84.20, due on the 28th. "
                                    "Last month you paid GBP 83.10."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "unused_subscription",
                        "title": "FitLife gym unused for 90 days",
                        "detail": (
                            "You are paying GBP 38.00 a month for FitLife and there is no "
                            "recorded visit in the last 90 days — GBP 456 a year."
                        ),
                        "confidence": 0.88,
                        "merchant": "FitLife",
                        "category": "fitness",
                        "amount_minor": 3800,
                        "currency": "GBP",
                        "evidence": [
                            {
                                "signal_id": SIG_FITLIFE,
                                "excerpt": (
                                    "Monthly charge of GBP 38.00. No visit recorded against "
                                    "this membership in the last 90 days."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "trial_converting",
                        "title": "Streamly trial converts in 3 days",
                        "detail": (
                            "Your Streamly free trial ends in three days and becomes "
                            "GBP 12.99 a month unless it is cancelled first."
                        ),
                        "confidence": 0.92,
                        "merchant": "Streamly",
                        "category": "streaming",
                        "amount_minor": 1299,
                        "currency": "GBP",
                        "evidence": [
                            {
                                "signal_id": SIG_STREAMLY,
                                "excerpt": (
                                    "After 3 days you will be charged GBP 12.99 a month "
                                    "unless you cancel before then."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "appointment_needs_reply",
                        "title": "Dental check-up needs confirming",
                        "detail": (
                            "Bridge Street Dental want the 2nd at 09:15 confirmed at least "
                            "48 hours in advance."
                        ),
                        "confidence": 0.9,
                        "merchant": "Bridge Street Dental",
                        "category": "health",
                        "evidence": [
                            {
                                "signal_id": SIG_DENTIST,
                                "excerpt": (
                                    "Your appointment is on the 2nd at 09:15. The practice "
                                    "asks you to confirm at least 48 hours in advance."
                                ),
                            }
                        ],
                    },
                ]
            },
        )
    ],
    final_text="Four findings.",
)

BILL_ANALYST = MockScript(
    steps=[
        # Silent: the bill is normal, so it is recorded and nobody is disturbed.
        ScriptedStep(
            "file_record",
            {
                "merchant": "British Gas",
                "note": "GBP 84.20 due the 28th; GBP 1.10 above last month.",
                "rationale": (
                    "This bill is in line with last month, so Quiet Hours recorded it "
                    "and left it alone."
                ),
            },
        ),
        ScriptedStep(
            "ActionPlan",
            {
                "actions": [
                    {
                        "kind": "file_record",
                        "summary": "Recorded British Gas bill of GBP 84.20",
                        "rationale": (
                            "The amount is within GBP 1.10 of last month, which is normal "
                            "seasonal variation, so there was nothing to ask you about."
                        ),
                        "risk": "silent",
                        "merchant": "British Gas",
                        "reversible": True,
                        "evidence": [
                            {
                                "signal_id": SIG_GAS,
                                "excerpt": "Your bill for this month is GBP 84.20, due on the 28th.",
                            }
                        ],
                    }
                ],
                "note": "",
            },
        ),
    ],
    final_text="Gas bill checked and recorded.",
)

NEGOTIATOR = MockScript(
    steps=[
        # The one action that spends the user's money. This is the interrupt.
        ScriptedStep(
            "cancel_subscription",
            {
                "merchant": "FitLife",
                "monthly_amount_minor": 3800,
                "reason": "No recorded visit in 90 days.",
                "rationale": (
                    "You have paid GBP 38.00 a month since May without a single recorded "
                    "visit — GBP 456 a year. Cancelling stops that, but you would lose "
                    "the membership and any joining rate you are on."
                ),
            },
        ),
        # Silent: the trial is worth noting, not worth interrupting anyone over.
        ScriptedStep(
            "file_record",
            {
                "merchant": "Streamly",
                "note": "Free trial converts to GBP 12.99/mo in 3 days.",
                "rationale": (
                    "Noted so the conversion is not a surprise. Nothing is cancelled — "
                    "you may well want to keep it."
                ),
            },
        ),
        ScriptedStep(
            "ActionPlan",
            {
                "actions": [
                    {
                        "kind": "cancel_subscription",
                        "summary": "Cancel FitLife (GBP 38.00/mo)",
                        "rationale": (
                            "Unused for 90 days, costing GBP 456 a year."
                        ),
                        "risk": "confirm",
                        "merchant": "FitLife",
                        "reversible": False,
                        "estimated_impact_minor": 45600,
                        "currency": "GBP",
                        "evidence": [
                            {
                                "signal_id": SIG_FITLIFE,
                                "excerpt": "No visit recorded against this membership in the last 90 days.",
                            }
                        ],
                    },
                    {
                        "kind": "file_record",
                        "summary": "Noted Streamly trial converting in 3 days",
                        "rationale": (
                            "Recorded so the first GBP 12.99 charge is not a surprise."
                        ),
                        "risk": "silent",
                        "merchant": "Streamly",
                        "reversible": True,
                        "evidence": [
                            {
                                "signal_id": SIG_STREAMLY,
                                "excerpt": "After 3 days you will be charged GBP 12.99 a month.",
                            }
                        ],
                    },
                ],
                "note": "",
            },
        ),
    ],
    final_text="Subscriptions reviewed.",
)

SCHEDULER = MockScript(
    steps=[
        # NOTIFY: external but harmless and reversible, so it does not interrupt.
        ScriptedStep(
            "set_reminder",
            {
                "subject": "Confirm dental check-up with Bridge Street Dental",
                "remind_at": "2026-08-29T09:00:00Z",
                "rationale": (
                    "Set for three days before, which still leaves time to confirm "
                    "within the practice's 48-hour window."
                ),
            },
        ),
        ScriptedStep(
            "ActionPlan",
            {
                "actions": [
                    {
                        "kind": "set_reminder",
                        "summary": "Reminder to confirm dental check-up",
                        "rationale": (
                            "The practice needs 48 hours' notice. If nobody confirms, "
                            "the slot is given away."
                        ),
                        "risk": "notify",
                        "merchant": "Bridge Street Dental",
                        "reversible": True,
                        "evidence": [
                            {
                                "signal_id": SIG_DENTIST,
                                "excerpt": "The practice asks you to confirm at least 48 hours in advance.",
                            }
                        ],
                    }
                ],
                "note": "",
            },
        ),
    ],
    final_text="Dates handled.",
)

BRIEF = MockScript(
    steps=[
        ScriptedStep(
            "BriefDraft",
            {
                # The brief node only ever runs on a *completed* graph — if a
                # decision were outstanding the run would still be suspended and
                # this node would not have been reached. So a headline claiming
                # something needs the user is false by construction here, which
                # is exactly what `brief.md` forbids: pending decisions are
                # rendered from real records, never from this text.
                "headline": "Today's admin is done — nothing needs you",
                "handled_silently": [
                    "Recorded the British Gas bill of GBP 84.20, due the 28th",
                    "Noted the Streamly trial converting in 3 days",
                    "Set a reminder to confirm your dental check-up",
                ],
                "note": "",
            },
        )
    ],
    final_text="Brief ready.",
)


SCRIPTS: dict[str, MockScript] = {
    "ingest": INGEST,
    "triage": TRIAGE,
    "bill_analyst": BILL_ANALYST,
    "negotiator": NEGOTIATOR,
    "scheduler": SCHEDULER,
    "brief": BRIEF,
}


def script_for(node_id: str) -> MockScript:
    """The mock script for one node.

    An unknown node gets an empty script rather than an error: in live mode the
    scripts are unused anyway, and a node with nothing to say is a survivable
    outcome where a crash at graph-construction time is not.
    """
    return SCRIPTS.get(node_id, MockScript())
