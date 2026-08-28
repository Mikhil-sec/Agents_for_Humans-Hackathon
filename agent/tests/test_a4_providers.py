"""A4 — the consumer side of Lane C's provider bundle.

Lane C's `integrations/base.py` calls itself "a contract with Lane A", and it is
real: the `Providers` Protocols exist and are stable. Only the implementations
behind `get_providers()` are outstanding. So A4 is written and tested here
against the published interface, and goes live the moment Yorvan implements it —
no Lane A change required.

These tests supply a fake bundle satisfying the Protocols. That is the point:
if Lane C's real implementation satisfies the same Protocols, these pass against
it too, and if it does not, `test_the_fake_bundle_satisfies_lane_cs_protocols`
fails and tells us the contract drifted.

The two rules being pinned:

* **Mock mode falls back; live mode raises.** A live run quietly reasoning over
  demo data would produce real decision cards about merchants the household has
  never heard of.
* **`household_id` comes from `invocation_state`, never from a tool argument.**
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from quiet_hours_contracts import Money, Signal, SignalKind

from quiet_hours_agent import providers as providers_module
from quiet_hours_agent import signals as signals_module
from quiet_hours_agent.providers import ProvidersUnavailable, get_providers
from quiet_hours_agent.signals import SignalSourcesUnavailable, load_signals_for
from quiet_hours_agent.tools import actions

HOUSEHOLD = "hh_demo"
NOW = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clean_cache():
    providers_module.reset_cache()
    yield
    providers_module.reset_cache()


# --------------------------------------------------------------------------
# A fake bundle shaped exactly like Lane C's published Protocols
# --------------------------------------------------------------------------


def signal(signal_id: str, *, kind: SignalKind, source: str, when: datetime) -> Signal:
    return Signal(
        signal_id=signal_id,
        household_id=HOUSEHOLD,
        kind=kind,
        occurred_at=when,
        ingested_at=when,
        source=source,
        subject=f"subject for {signal_id}",
        body=f"body for {signal_id}",
        merchant="Acme",
        amount=Money(amount_minor=1000, currency="GBP"),
    )


class FakeEmail:
    def __init__(self) -> None:
        self.drafts: list[tuple] = []

    def fetch_since(self, household_id, since, limit=200):
        return [signal("sig_email", kind=SignalKind.EMAIL, source="gmail", when=NOW)]

    def create_draft(self, household_id, to, subject, body, in_reply_to=None):
        self.drafts.append((household_id, to, subject, body))
        return "draft_1"

    def get_thread(self, household_id, thread_ref):
        return []


class FakeTransactions:
    def fetch_since(self, household_id, since, limit=500):
        # Deliberately out of order relative to the email, to prove the merge sorts.
        return [
            signal(
                "sig_txn",
                kind=SignalKind.TRANSACTION,
                source="bank",
                when=NOW.replace(hour=1),
            )
        ]

    def merchant_history(self, household_id, merchant, months=12):
        return []


class FakeCalendar:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def fetch_between(self, household_id, start, end):
        return [
            signal(
                "sig_cal",
                kind=SignalKind.CALENDAR_EVENT,
                source="calendar",
                when=NOW.replace(hour=23),
            )
        ]

    def find_free_slots(self, household_id, start, end, duration_minutes):
        return []

    def create_event(self, household_id, title, start, end, notes=None):
        self.events.append((household_id, title, start, end))
        return "evt_1"


class FakePayments:
    def __init__(self) -> None:
        self.scheduled: list[tuple] = []

    def schedule_payment(self, household_id, payee, amount, due_at, reference=None):
        self.scheduled.append((household_id, payee, amount, due_at))
        return "pay_1"

    def cancel_scheduled_payment(self, household_id, payment_id):
        return True


class FakeSubscriptions:
    def __init__(self) -> None:
        self.cancelled: list[tuple] = []
        self.downgraded: list[tuple] = []

    def cancel(self, household_id, merchant, note=None):
        self.cancelled.append((household_id, merchant, note))
        return "rcpt_1"

    def downgrade(self, household_id, merchant, target_plan):
        self.downgraded.append((household_id, merchant, target_plan))
        return "rcpt_2"


class FakeBundle:
    def __init__(self) -> None:
        self.email = FakeEmail()
        self.transactions = FakeTransactions()
        self.calendar = FakeCalendar()
        self.payments = FakePayments()
        self.subscriptions = FakeSubscriptions()
        self.mode = "mock"

    @property
    def is_live(self) -> bool:
        return False


@pytest.fixture
def bundle(monkeypatch) -> FakeBundle:
    """Install a fake bundle as though Lane C had shipped."""
    fake = FakeBundle()
    monkeypatch.setattr(providers_module, "get_providers", lambda mode=None: fake)
    monkeypatch.setattr(signals_module, "get_providers", lambda mode=None: fake)
    monkeypatch.setattr(actions, "get_providers", lambda mode=None: fake)
    return fake


class Context:
    """The slice of `ToolContext` the governed tools read."""

    def __init__(self, household_id: str | None = HOUSEHOLD) -> None:
        self.invocation_state: dict = {"provider_mode": "mock"}
        if household_id is not None:
            self.invocation_state["household_id"] = household_id


def call(tool_fn, **kwargs) -> str:
    """Invoke a `@tool`-decorated function directly, past the decorator."""
    inner = getattr(tool_fn, "_tool_func", None) or getattr(tool_fn, "__wrapped__", tool_fn)
    return inner(**kwargs)


# --------------------------------------------------------------------------
# The contract with Lane C
# --------------------------------------------------------------------------


def test_the_fake_bundle_satisfies_lane_cs_protocols():
    """If this fails, `integrations/base.py` changed and Lane A's calls are stale.

    That file says edits to it need announcing in `DECISIONS.md` first, so this
    failing is a process signal as much as a code one.
    """
    from quiet_hours_integrations.base import (
        CalendarProvider,
        EmailProvider,
        PaymentProvider,
        SubscriptionProvider,
        TransactionProvider,
    )

    fake = FakeBundle()
    assert isinstance(fake.email, EmailProvider)
    assert isinstance(fake.transactions, TransactionProvider)
    assert isinstance(fake.calendar, CalendarProvider)
    assert isinstance(fake.payments, PaymentProvider)
    assert isinstance(fake.subscriptions, SubscriptionProvider)


def test_email_provider_still_has_no_send_method():
    """The safety guarantee is the *absence* of the method. If Lane C ever adds a
    `send`, this fails and the conversation happens before anything ships."""
    from quiet_hours_integrations.base import EmailProvider

    assert not hasattr(EmailProvider, "send")
    assert not hasattr(FakeEmail(), "send")


# --------------------------------------------------------------------------
# Falling back, and refusing to
# --------------------------------------------------------------------------


def test_mock_mode_falls_back_when_lane_c_is_absent():
    """Today's real state: `get_providers()` raises, and the demo still works."""
    assert get_providers("mock") is None

    loaded = load_signals_for(HOUSEHOLD, mode="mock")
    assert loaded, "the in-lane stand-in must still produce a day's signals"


def test_live_mode_refuses_to_fall_back():
    """A live run over demo data would raise real decision cards about merchants
    the household has never heard of."""
    with pytest.raises(ProvidersUnavailable):
        get_providers("live")


def test_live_signal_loading_refuses_to_fall_back():
    with pytest.raises(ProvidersUnavailable):
        load_signals_for(HOUSEHOLD, mode="live")


def test_the_absence_warning_is_logged_once_per_process(caplog):
    """Six specialists times eleven tools times four replay weeks is a lot of
    identical warnings, and a log that repeats itself is a log nobody reads."""
    with caplog.at_level("WARNING"):
        get_providers("mock")
        providers_module._cache.clear()  # force a rebuild, keep the warned set
        get_providers("mock")

    assert sum("falling back" in record.message for record in caplog.records) == 1


@pytest.mark.parametrize(
    ("raised", "falls_back"),
    [
        (FileNotFoundError("fixtures/inbox/*.json"), True),
        (NotImplementedError("not written yet"), True),
        (ValueError("household.json failed validation"), False),
    ],
    ids=["fixtures-absent", "providers-absent", "fixtures-malformed"],
)
def test_the_fallback_covers_lane_c_being_absent_not_lane_c_being_broken(
    monkeypatch, raised, falls_back
):
    """`require_fixture_set()` raises `FixturesNotFoundError` — a `FileNotFoundError`
    — when the raw files are not seeded yet, and that is a documented stand-in
    condition. A malformed `household.json` is a defect in a bundle that *does*
    exist, and downgrading mock mode to the stand-in would hide it behind a demo
    that still runs but is quietly worse.
    """
    from quiet_hours_integrations import registry

    def explode(*args, **kwargs):
        raise raised

    monkeypatch.setattr(registry, "get_providers", explode)
    providers_module.reset_cache()

    if falls_back:
        assert get_providers("mock") is None
    else:
        with pytest.raises(ValueError):
            get_providers("mock")


def test_every_source_failing_is_an_error_not_a_quiet_day(bundle):
    """Zero actions scores as 1.0 autonomy. A bundle-level fault — the wrong
    `household_id`, a moved fixtures directory — would otherwise publish itself as
    a perfect autonomy score rather than as a bug."""

    def explode(*args, **kwargs):
        raise ValueError("'hh_wrong' is not the demo household")

    bundle.email.fetch_since = explode
    bundle.transactions.fetch_since = explode
    bundle.calendar.fetch_between = explode

    with pytest.raises(SignalSourcesUnavailable):
        load_signals_for(HOUSEHOLD, mode="mock", now=NOW)


# --------------------------------------------------------------------------
# Reading through the providers
# --------------------------------------------------------------------------


def test_signals_come_from_all_three_readable_providers(bundle):
    loaded = load_signals_for(HOUSEHOLD, mode="mock", now=NOW)

    assert {s.signal_id for s in loaded} == {"sig_email", "sig_txn", "sig_cal"}


def test_signals_are_merged_in_chronological_order(bundle):
    """The rendered context is read top to bottom by every node, so it has to read
    chronologically whatever order the providers returned."""
    loaded = load_signals_for(HOUSEHOLD, mode="mock", now=NOW)

    assert [s.signal_id for s in loaded] == ["sig_txn", "sig_email", "sig_cal"]


def test_one_broken_provider_does_not_lose_the_others(bundle, caplog):
    """An unreachable bank must not stop the agent noticing that a dental
    appointment needs confirming."""

    def explode(*args, **kwargs):
        raise RuntimeError("bank is down")

    bundle.transactions.fetch_since = explode

    with caplog.at_level("WARNING"):
        loaded = load_signals_for(HOUSEHOLD, mode="mock", now=NOW)

    assert {s.signal_id for s in loaded} == {"sig_email", "sig_cal"}
    assert any("transactions" in record.message for record in caplog.records)


# --------------------------------------------------------------------------
# Acting through the providers
# --------------------------------------------------------------------------


def test_draft_email_creates_a_draft_and_never_sends(bundle):
    result = call(
        actions.draft_email,
        tool_context=Context(),
        recipient="billing@fitlife.example",
        subject="Cancellation request",
        body="Please cancel my membership.",
    )

    assert bundle.email.drafts == [
        (HOUSEHOLD, "billing@fitlife.example", "Cancellation request", "Please cancel my membership.")
    ]
    assert "nothing was sent" in result


def test_pay_bill_creates_a_request_and_moves_no_money(bundle):
    result = call(
        actions.pay_bill,
        tool_context=Context(),
        merchant="British Gas",
        amount_minor=8420,
        due_date="2026-08-28",
    )

    household_id, payee, amount, _due = bundle.payments.scheduled[0]
    assert (household_id, payee) == (HOUSEHOLD, "British Gas")
    assert amount == Money(amount_minor=8420, currency="GBP")
    assert "No money has moved" in result


def test_cancel_subscription_reaches_the_provider(bundle):
    call(
        actions.cancel_subscription,
        tool_context=Context(),
        merchant="FitLife",
        monthly_amount_minor=3800,
        reason="No visits in 90 days",
    )

    assert bundle.subscriptions.cancelled == [(HOUSEHOLD, "FitLife", "No visits in 90 days")]


def test_downgrade_plan_reaches_the_provider(bundle):
    call(
        actions.downgrade_plan,
        tool_context=Context(),
        merchant="Streamly",
        to_plan="Basic",
        from_plan="Premium",
    )

    assert bundle.subscriptions.downgraded == [(HOUSEHOLD, "Streamly", "Basic")]


def test_a_reminder_becomes_a_short_calendar_event(bundle):
    """`CalendarProvider` has no reminder concept. A short event is the closest
    honest mapping onto the interface Lane C published — inventing a
    `create_reminder` method would be Lane A editing Lane C's contract."""
    call(
        actions.set_reminder,
        tool_context=Context(),
        subject="Confirm dental check-up",
        remind_at="2026-08-29T09:00:00Z",
    )

    household_id, title, start, end = bundle.calendar.events[0]
    assert household_id == HOUSEHOLD
    assert "Confirm dental check-up" in title
    assert (end - start).total_seconds() == actions.REMINDER_MINUTES * 60


def test_add_calendar_event_reaches_the_provider(bundle):
    call(
        actions.add_calendar_event,
        tool_context=Context(),
        title="Dental check-up",
        starts_at="2026-09-02T09:15:00Z",
    )

    assert bundle.calendar.events[0][1] == "Dental check-up"


def test_a_malformed_date_from_the_model_does_not_crash_an_approved_action(bundle):
    """These bodies run *after* the policy gate, sometimes after the user has
    explicitly approved. Crashing on a bad date would fail an action the user said
    yes to, and the audit trail would record it as an error they cannot act on."""
    call(
        actions.add_calendar_event,
        tool_context=Context(),
        title="Dental check-up",
        starts_at="next Tuesday-ish",
    )

    assert bundle.calendar.events, "the event should still have been created"


# --------------------------------------------------------------------------
# Tenancy
# --------------------------------------------------------------------------


def test_a_tool_with_no_household_does_not_reach_a_provider(bundle):
    """A run that cannot say whose data it is holding has no business touching
    anyone's — the same rule `tools/ingest.py` applies to reading."""
    call(
        actions.cancel_subscription,
        tool_context=Context(household_id=None),
        merchant="FitLife",
        monthly_amount_minor=3800,
    )

    assert bundle.subscriptions.cancelled == []


def test_household_id_is_never_taken_from_a_tool_argument():
    """A model that can pass a `household_id` can be talked into passing someone
    else's, so no governed tool exposes one."""
    import inspect

    for tool_fn in actions.ACTION_TOOLS:
        inner = getattr(tool_fn, "_tool_func", None) or getattr(
            tool_fn, "__wrapped__", tool_fn
        )
        assert "household_id" not in inspect.signature(inner).parameters, tool_fn


# --------------------------------------------------------------------------
# The tools Lane C has no method for
# --------------------------------------------------------------------------


def test_the_two_unmapped_tools_still_work_in_lane(bundle):
    """`reschedule_appointment` and `dispute_charge` have no provider method.

    Lane A must not invent one — `LANE_A_AGENT.md`: "If a provider method is
    missing, ask Lane C; do not add it yourself." The ask is recorded in
    `PROGRESS_A.md`. Until then these stay in-lane, and the policy gate in front
    of them is real regardless.
    """
    assert "Reschedule requested" in call(
        actions.reschedule_appointment,
        merchant="Bridge Street Dental",
        to_datetime="2026-09-03T10:00:00Z",
    )
    assert "Dispute prepared" in call(
        actions.dispute_charge, merchant="Acme", amount_minor=5000, reason="Never ordered this"
    )
