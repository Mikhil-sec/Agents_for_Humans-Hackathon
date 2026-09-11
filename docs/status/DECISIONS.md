# Decision log

Cross-cutting decisions that affect more than one lane. **Append new sections at the bottom. Never edit an existing entry** — if a decision is reversed, write a new entry that supersedes it and link back.

Anything here is binding on all lanes. If you disagree with a decision, open a new entry proposing the change rather than quietly working around it.

Use this for: contract changes, dependency additions everyone will use, changes to the risk tiers, changes to the demo narrative, deployment target changes, scope cuts.

---

## 2026-08-21 — Project shape

**Decision:** Build "Quiet Hours", an autonomous household-admin agent for the *Everyday Agents* track. Three lanes: A (agent), B (API + web), C (integrations + infra), with a documented two-person fallback in `docs/lanes/TWO_PERSON_FALLBACK.md`.

**Why:** The track rewards agents that "run quietly in the background and only ping you when there's a real decision to make". Strands' `interrupt()` primitive plus durable session management maps onto that description almost exactly, which makes it both a natural fit and a non-obvious use of the SDK.

**Affects:** everyone.

---

## 2026-08-21 — The interrupt is the product

**Decision:** The differentiating mechanic is **earned autonomy**. Every approval can create a policy; the policy engine then handles that class of action silently; the interrupt rate falls measurably over four simulated weeks. The autonomy trend chart is the demo's headline visual.

**Why:** Most hackathon entries will be a chatbot with tools attached. A visible, quantified reduction in how often the agent bothers you is a direct, demonstrable answer to the brief's own thesis, and it is hard to build without exactly the Strands features we are using.

**Affects:** A owns the mechanic, B owns the chart, C owns the fixture data that produces the curve. All three are required for the demo to land.

---

## 2026-08-21 — The policy engine is deterministic code, not a model

**Decision:** `agent/quiet_hours_agent/policy.py` contains no LLM call. It is pure functions over an explicit policy table.

**Why:** Learned autonomy must be auditable, explainable and revocable. A model deciding whether it needs permission is precisely the thing a user would not trust with their bank account — and a prompt can be argued out of a safety rule, whereas an `if` statement cannot. This is also a point worth making explicitly to judges.

**Consequence:** No policy may auto-approve a `NEVER_AUTO` action. Enforced in code and covered by a named test.

**Affects:** A primarily; B renders the policies this produces.

---

## 2026-08-21 — Mock mode is the default and must never break

**Decision:** Every external dependency sits behind a provider interface with `mock` and `live` implementations. `git clone && make demo` must produce a fully working system with no AWS account and no credentials.

**Why:** The rules require the project to install and run consistently, and a judge with four minutes will not configure OAuth. Mock mode is our guarantee that they see the product working.

**Affects:** C builds it, A consumes it, B mirrors it with `fixtures_server.py`.

---

## 2026-08-21 — Safety posture: drafts and requests, never sends and transfers

**Decision:** Even in live mode the agent creates email *drafts* and *scheduled payment requests*. The live Gmail provider has no send path in the codebase at all.

**Why:** An agent with unattended access to someone's email and money is a liability we are not going to ship in a hackathon, and the absence of the code is a stronger guarantee than a config flag. Stating this plainly in the README reads as engineering judgement rather than as a limitation.

**Affects:** C implements it, A must not work around it, B should surface it in the UI copy.

---

## 2026-08-21 — Money is integer minor units

**Decision:** `Money(amount_minor: int, currency: str)`. Never floats, anywhere, in any lane.

**Why:** Float arithmetic on money produces off-by-a-penny bugs that are painful to track down, and we are demoing a financial product.

**Affects:** everyone. `formatMoney()` in the TypeScript contracts is the only place division by 100 should occur.

---

## 2026-08-24 — DynamoDB single-table layout

**Decision:** One table, name from `QH_TABLE_NAME` (default `quiet-hours`). A record's own
id is the partition key; a GSI named `gsi1` answers every household query. The contract
model is stored as **JSON text** in a `body` attribute.

| Attribute | Example | Purpose |
|---|---|---|
| `pk` / `sk` | `DECISION#dec_abc` | the record's own id; both the same |
| `gsi1pk` | `HH#hh_demo#DECISION` | one household's records of one type |
| `gsi1sk` | `2026-08-24T07:15:00Z` | the record's timestamp, so lists come back ordered |
| `type` | `DECISION` | one of `ACTION`, `DECISION`, `ACTIVITY`, `POLICY`, `RUN` |
| `body` | `{"decision_id": ...}` | the contract model, `model_dump_json()` |

**Why id-as-partition-key:** `get_decision(decision_id)` takes no `household_id` — Lane B's
`POST /api/decisions/{id}/respond` only has the id from the URL. Partitioning by household
would make every read a scan or a second lookup. The household query is the *secondary*
access pattern, so it lives on the secondary index.

**Why JSON text rather than typed attributes:** DynamoDB has no float type and
`Finding.confidence` is a float. Typed attributes would mean a `Decimal` conversion on every
write and every read, in both Lane A's code and Lane B's, forever. Storing
`model_dump_json()` output means the bytes in the table are exactly the frozen contract
shape, and both lanes parse them with the same pydantic models. It costs the ability to
query on an inner field, which nothing in the product does.

**Status filtering is client-side.** `list_pending_decisions` reads the household's
decisions and filters on `status`. Folding status into `gsi1pk` would make resolving a card
a delete-and-reinsert across two partitions, and a crash between the two would lose the card.

**Reference implementation:** `agent/quiet_hours_agent/store.py::DynamoStore`, with the
`Store` Protocol at the top of the same file. Tests in
`agent/tests/test_persistence_live.py`.

**Affects:** A writes it (done), B reads it, C provisions the table and the `gsi1` index in
CDK. **No pagination** — every list method takes the first page, which is right for a demo
household and would need revisiting for a year of activity.

---

## 2026-08-24 — main was force-pushed away, and how it was restored

**What happened:** `main` was force-pushed to an unrelated single commit containing 13
files — Lane B's `api/` and `web/` work plus a LICENSE and an architecture note. That
removed `/contracts`, `/agent`, `/integrations`, `/fixtures`, `/infra`, `/docs`, the
`Makefile` and every `AGENTS.md` from the default branch. The cause was pushing from a
directory that was never a clone of this repository.

**Decision:** the orphan commit was **merged** into the real history rather than reverted,
so Lane B's work and its authorship are both preserved. `main` now has two roots. No force
push was needed to restore it, because merging made the orphan an ancestor.

**Nothing was lost.** Three backup branches exist and should not be deleted until everyone
has confirmed their work is present:

| Branch | What it holds |
|---|---|
| `backup/main-before-force-push` | `main` exactly as it was before |
| `backup/diya-first-commit` | the force-pushed commit, standalone |
| `backup/miks-branch` | Lane A's branch at the time |

**Resolutions made during the merge:** the project's MIT `LICENSE` was kept over an
incoming truncated Apache 2.0 header (a fresh-repository default, not a relicensing
decision); `api/__pycache__/*.pyc` were dropped as build artifacts already in
`.gitignore`.

**How to avoid a repeat:** always `git clone` this repository rather than pushing a local
folder into it, work on a lane branch (`a/`, `b/`, `c/`), and open a PR. Branch protection
on `main` was removed on 22 Aug; **turning it back on would have prevented this entirely**
and is recommended.

**Affects:** everyone.

---

## 2026-08-24 — /fixtures is generated from a real agent run until Lane C's seeder lands

**Decision:** `make fixtures` tries `quiet_hours_integrations.mock.seed` first and falls
back to `python -m quiet_hours_agent.export_fixtures`, which runs the agent in mock mode
and writes what the run actually produced.

**Why:** Lane C's seeder is still a stub, so `make fixtures` failed, `/fixtures` held no
JSON, and every Lane B screen returned 404. `make demo` was dead at step one — the thing a
judge runs, and root `AGENTS.md` rule 3.

**Why generated rather than hand-written:** everything written comes out of `store.py`,
which only ever holds validated contract models, so the fixtures are contract-correct by
construction. Hand-written fixtures drift from `/contracts` silently.

**This is not a replacement for Lane C's seeder.** It reads nothing from `/fixtures` and
invents no inbox. When Yorvan's seeder lands it takes precedence again with no further
change.

**Affects:** A generates it, B reads it, C supersedes it.

---

## 2026-08-28 — /fixtures is generated in two stages, permanently

**Decision:** `make fixtures` runs Lane C's seeder and then Lane A's exporter, in
that order, and both are required.

```
quiet_hours_integrations.mock.seed   ->  household.json, inbox/*.json,
                                          transactions.json, calendar.json,
                                          merchant_history.json
quiet_hours_agent.export_fixtures    ->  decisions.json, activity.json,
                                          policies.json, runs.json,
                                          daily_brief.json
```

**This supersedes the 24 August entry**, which framed `export_fixtures` as a
temporary stand-in that Lane C's seeder would replace outright. It is stage two,
not a stopgap.

**Why:** the two halves of `/fixtures` are different kinds of artifact. The first
five are the household's world before the agent touches it — Lane C's script, and
authoring them is the job. The last five are a record of what the agent did in that
world: a decision card exists because a signal was ingested, a finding was formed,
an action was proposed and the policy engine declined to auto-approve it, and it
carries a real `interrupt_id`, `session_id` and evidence citing real signal ids.
Hand-authoring those would assert the autonomy curve rather than measure it, and the
"only interrupts when there is a real decision" claim is the one a judge will probe
hardest.

**Scope, stated plainly:** landing Lane C's mock providers does not by itself move
the four-week replay onto Lane C's data. `signals.py::load_signals_for` resolves a
scripted scenario before consulting the providers, so the replay runs on Lane A's
`scenarios.py`; the provider path serves the single-day run. Mock mode drives a
scripted model — zero-credential `make demo` is root `AGENTS.md` rule 3 — and those
scripts are keyed to signal ids, so the replay can only reason over Lane C's world
once Lane A's weekly scripts are re-keyed onto frozen Lane C ids. That is a
follow-on, tracked as A8, and it requires stable `signal_id`s, week membership on
every raw item, and a scenario-to-signal-id manifest from Lane C.

**Failure mode this closes:** `providers.py` fails open in mock mode by design, so
the first bundle Lane C returned could have silently replaced Lane A's stand-in with
an empty day. Lane C closed it from their side in `c/mock-providers` with an eager
`require_fixture_set()` in `build_mock_providers`, which validates all five raw files
before a bundle is handed back, so an unseeded `/fixtures` raises at build time
rather than returning providers that each fail on first read.

Lane A narrowed to match. The mock-mode fallback now covers
`(NotImplementedError, FileNotFoundError)` only — the two "Lane C is not here yet"
conditions — and any other failure propagates in both modes, because the fallback is
for Lane C being *absent*, not for Lane C being *broken*. Separately,
`signals.py::_from_providers` still tolerates one dead source but now raises
`SignalSourcesUnavailable` when all three fail: a bundle-level fault hits every
provider equally, and an empty signal list reads down the whole stack as a quiet day,
which `WeekResult.autonomy_rate` scores as 1.0. A caller bug would otherwise publish
itself as a perfect autonomy score.

**Outstanding, and it lands with `c/fixtures-full`:** Lane A anchors its read window
to wall-clock `now` (`LOOKBACK`, `CALENDAR_HORIZON`, and `tools/ingest.py` passing no
`now`), while the fixture world is anchored to a fixed `DEFAULT_AS_OF` of 2026-08-26
with the last signal dated 23 August. As written, the day run will read zero signals
from a fully seeded `/fixtures` — three empty lists, no exception — and report a
quiet day. Lane C has been asked to expose the reference date on the bundle as
`Providers.as_of` so mock mode can anchor to the fixture world's clock; Lane A makes
the change once that seam exists.

**Affects:** C writes the five raw files and freezes their ids; A runs stage two and
owns the `Makefile` change; B reads the result and should expect `runs.json` to gain
its fourth point when A8 lands.

---

## 2026-08-28 — the vertical slice moves to 7 September; the submission date does not

**Decision:** the end-to-end slice milestone moves from **31 August to 7 September**.
Everything after it — Phase 3 polish from the 8th, the 12 September feature freeze,
the submission itself — stays exactly where it was.

**Why:** all three of us have been busier than the original plan assumed. A week is
recoverable now; discovering on 6 September that the slice never closed is not.

**What it costs, stated plainly so nobody is surprised:** the submission date is
fixed, so this week comes out of **Phase 2 depth**, not out of the end. Phase 1 and
Phase 2 now overlap, and anything in Phase 2 that is not on the critical path for the
slice is the first thing to cut. Lane A's graph, policy learning and replay are
already done, so the compression falls on B and C.

**This date cannot move again.** A second slip has nowhere to go and lands on polish
and the video — the two things judges actually see. If the 7th looks at risk, cut
scope using `docs/lanes/TWO_PERSON_FALLBACK.md` rather than moving the date.

**Unchanged:** record the slice working the day it closes, as video insurance.

**Affects:** everyone. `docs/ROADMAP.md` updated. The critical path runs through Lane
B — `web/` has no `package.json` and cannot install, and `POST /api/decisions/{id}/respond`
is still a stub; the slice cannot close until both are real.

---

## 2026-09-07 — findings get their ids before the specialists run, not after

**Decision:** triage's findings are promoted into contract `Finding`s by a
`FindingRecorder` hook on `AfterNodeCallEvent`, between triage completing and the
first specialist starting. `graph.harvest()` reuses that list instead of minting a
second set of ids.

**Why:** findings used to get their ids in `harvest()`, which runs after the whole
graph. So while a specialist was calling `cancel_subscription`, no finding existed to
point at, and `PolicyHook` had no choice but to synthesise a `ProposedAction` with
`finding_id="unbacked"` and a placeholder `Evidence` reading *"Tool call
cancel_subscription with ['merchant', 'monthly_amount_minor', 'rationale', 'reason']"*.
That string was what the user read under "why am I being asked this", on **every card
the product has ever raised**.

**Affects Lane B directly.** `DecisionCard.evidence` now carries a real `signal_id`
and a quoted line from the household's own inbox, so the card can render its evidence
rather than hiding the field. The action also carries `params["category"]` copied from
its finding, which is what a `CATEGORY`-scoped policy is matched against — previously
only `tag_merchant` supplied one, so that scope was nearly unreachable.

**Note 1 in `graph.py` still holds:** `PolicyHook` goes on each node `Agent`, never on
the `GraphBuilder`. `FindingRecorder` is on the builder precisely because it is a
multi-agent hook and governs nothing — it only assigns identity, which is code's job.

## 2026-09-07 — `estimated_annual_savings` counts what executed, not what was proposed

**Decision:** `RunStats.estimated_annual_savings` is counted from
`PolicyHook.executed` — actions whose tool call actually ran and succeeded, whether
silently or because the user approved them. Recurring costs
(`cancel_subscription`, `downgrade_plan`, `close_account`) are annualised; a one-off
(`dispute_charge`) is counted once; `pay_bill` is money going out and is not a saving.

**Why:** the field has been declared in `/contracts` since the freeze and `null` on
every run the product has produced. Two rules make the number defensible. Counting
*proposals* would let the headline figure be inflated by asking for things rather than
by doing them, which is the exact behaviour this product exists to argue against.
Annualising a refund is the kind of arithmetic that makes a demo unbelievable to
anyone who checks it.

**Consequence worth knowing before the video:** the fixture set's fourth week reports
`null`, because its one cancellation is still pending. Answer the card and the number
appears. That is the intended behaviour and it is a better demo beat than a static
figure.

**Affects Lane B:** `runs.json` now populates the field for weeks 1–3
(GBP 611.88 / 107.88 / 336.00) and leaves week 4 null. Treat null as "nothing secured
yet", not as "not measured".

## 2026-09-07 — the run's clock comes from the fixture world, not the wall

**Decision:** `signals.resolve_now(explicit, bundle)` resolves a run's "now" in
priority order: an explicit argument, then `Providers.as_of`, then `QH_AS_OF`, then
wall clock. Every read window is anchored to it.

**Why:** Lane C's fixture world is anchored to a fixed reference date (2026-08-26).
A `LOOKBACK` measured from `datetime.now(UTC)` falls entirely after that world ends, so
all three providers return empty lists — and **an empty list is not an exception**. It
reads down the stack as a quiet day: no findings, no actions, and
`RunStats.autonomy_rate` scoring zero actions as a perfect **1.0**. Verified before the
fix: wall clock returned 0 signals, the anchored clock returns 2.

**Affects everyone.** A defect that publishes itself as a perfect autonomy score is the
worst kind this codebase can produce, so `export_fixtures` now refuses to write a
fixture set generated from a run that ingested no signals.
## 2026-09-11 — `as_of` is a day, the far edge lives in Lane A, and the replay stays scripted

Two linked decisions. The first is settled and implemented; the second is a **deferral**,
recorded because it is the opposite of what Lane A said it would do on 10 September.

### 1. The read window has a far edge, and Lane A applies it

**Decision:** `as_of` denotes a **day**, not an instant. Neither `EmailProvider.
fetch_since` nor `TransactionProvider.fetch_since` gains an `until`; instead
`signals.end_of_day()` clamps the two backward-looking reads in Lane A, and
`load_signals_for` takes a `lookback` so a caller can name the window's width.

Lane C's ruling (Yorvan, 11 Sept), taken as option (b) of the two Lane A offered.

**Why a day.** The day is this product's unit of time everywhere else — the run is
daily, the digest is daily, "Nothing needs you today" is the empty state, and the four
weeks exist only as buckets for the autonomy chart. Nothing in the product surfaces a
run's clock time to a user.

**Why in Lane A.** `/contracts` and the provider Protocols were frozen; widening one the
day before feature freeze is a larger blast radius than one filter in the consumer. It
also preserves the two signals Lane C dated deliberately after midnight on the reference
date — `sig_fitlife_renewal` and `sig_thetimes_reminder` at 08:00 — which a strict
`<= now` would have deleted along with the pending card a judge is meant to open on.

**The wart, recorded rather than hidden:** a run whose reference time is 07:00 will see
an email that arrived at 08:00. Invisible in the product today. An `until` on the
Protocol is the cleaner long-term fix and is Lane C's to make after the 15th.

**A real bug found while doing it.** The calendar was read `fetch_between(now, now +
CALENDAR_HORIZON)` — forward from `now` only. Anchored there it can never return
anything from earlier the same day, so a run dated at the end of a week saw an empty
calendar and Lane C's `dentist_clash` scenario (a CONFIRM in week 1) vanished with no
error. The window now starts at `since`. The daily run gains yesterday and today's
earlier hours, which it should always have had; the forward horizon is unchanged.

### 2. The four-week replay stays on Lane A's scripted weeks for the submission

**Decision:** the plumbing for a fixture-world replay is landed and tested —
`replay.Week`, `replay.fixture_weeks()`, and four windows that provably tile Lane C's
world and cover all 63 signals exactly once. **The re-key itself is deferred past the
15th.** `replay(weeks=None)` reaches the new path; nothing on the shipped demo path does.

**Why, and this is the part worth reading.** The re-key was described on both sides as
a one-line change once `as_of` was settled. It is not. `mock_reasoning.py` is a
*hardcoded* four-signal day — it cites `sig_gas_bill`, `sig_fitlife_charge`,
`sig_streamly_trial`, `sig_dentist_appt` regardless of which signals were actually
loaded. Pointing the replay at Lane C's world therefore yields four actions a week
whatever the window contains. A faithful re-key needs a deterministic reasoner over the
seeded world, which is new code, not a filter.

**And the curve it would produce is probably worse.** Counting from
`fixtures/scenarios.json` alone, the nine seeded scenarios fall 2 / 2 / 1 / 2 decisions
per week with 0 / 0 / 2 / 0 handled silently — a rate of 0%, 0%, 67%, 0%. That is not a
rising curve, and `ReplayResult.is_rising` would fail on it. It is Lane C's own §5
argument arriving at the chart: household bills are monthly, so a merchant-scoped policy
mostly never fires again, and there is not enough recurrence inside four weeks of one
household to carry an autonomy curve on merchant scope alone.

**What ships instead:** the scripted weeks, measured — 4 → 1 decisions, 43% → 86%
autonomy — with `replay.render()` now stating in its own output which of the two worlds
produced the curve rather than leaving a reader to assume.

**Consequence, owned rather than glossed:** Lane C's seeded world is currently read only
by a live agent run, not by the fixture set the demo screens are built from. That is a
genuine incoherence and closing it is the right post-hackathon task. Doing it on freeze
eve, against an unmeasured curve that the arithmetic says will fall, is not.

**What it would take, for whoever picks it up:** a rule-based finding/action derivation
over Lane C's signals, plus `CATEGORY` or `ACTION_KIND` policy scope doing the work that
merchant scope cannot. Both were already on Lane C's list.

## 2026-09-11 (later) — the hosted demo is a static export, not a deployment

**Decision:** the live demo link is **GitHub Pages serving `web/` as a static export**,
with the API reimplemented in the browser (`web/lib/staticBackend.ts`). Not Amplify, not
a hosted FastAPI, and not AgentCore.

**Why this and not the Amplify plan.** Diya's §5 was right that the judged path needs no
Bedrock — but it still needed the API hosted somewhere, `QH_CORS_ORIGINS` set, and AWS
credentials nobody on the team has been able to get working. Pages needs none of that.
It is a push and a repo setting, it costs nothing, and it cannot break in a way that
takes the rest of the submission with it.

**How it works, in one line:** every read and write in `web/lib/api.ts` already funnels
through a single `request()` function, so static mode is one branch there. Below it,
`staticBackend.ts` is a port of `api/app/backends/fixtures.py` and the route modules —
same `Page` envelope, same pagination, same error codes, same rules for expiring a card,
learning a policy and recomputing the brief.

**What actually works on the hosted page**, verified in a browser against a file server
mimicking Pages: all four screens; answering a card, which resolves it, creates the rule
the button previewed verbatim, writes the activity row and flips the headline to
"Nothing needs you today"; revoking a rule; and "Check now", which replays the five
progress frames the SSE endpoint sends, in order and at the same cadence. Zero console
errors, no horizontal overflow at 390px, dark mode intact.

**What it is not, and the page says so.** There is no agent behind it and no model. The
banner reads *"Hosted demo — the real screens, running in your browser from a recorded
agent run."* That is a requirement rather than a nicety: a judge is entitled to know what
they are looking at before drawing a conclusion from it. It is also the stronger move —
the thing being demonstrated is a policy engine that is *deliberately deterministic code*,
which is exactly the part that loses nothing by running in a browser.

**State** lives in `sessionStorage`: a reload keeps the visitor's answer, a new tab gets
the seeded world back with its pending card. A "Start over" button restores it on demand.

**Affects Lane B.** This edits `/web` — `lib/staticBackend.ts` (new), one branch each in
`lib/api.ts` and `lib/stream.ts`, a `DemoBanner` in `AppShell.tsx`, `next.config.ts`, and
`out/**` added to the ESLint ignores. **The default build is unchanged**: every addition
is behind `NEXT_PUBLIC_STATIC_DEMO=1`, and `make demo` was re-run and re-verified in a
browser afterwards, including answering a card against the real API. Mikhil authorised
the cross-lane edit explicitly; see `docs/status/FOR_DIYA_STATIC_DEMO.md`.

### AgentCore, for the record

Not done, and not for want of effort. There is no AWS CLI and no credentials on the
machine this was built on, `/infra` is Lane C's, and Bedrock still returns
`ValidationException: Operation not allowed` for every model — so a deployed agent would
fail its first request. The honest position for the submission is the one root
`AGENTS.md` already takes: mock mode is the judged path, it needs no credentials, and we
say so plainly.

## 2026-09-12 — strands-agents is pinned, and why CI was lying to us

**Found by removing `|| true` from CI**, within an hour of doing it. Worth writing down
because the failure was invisible for weeks and the cause is not what it looked like.

**Symptom.** `agent/tests/test_a1_interrupt_spike.py` failed in CI on both branches while
passing on every developer machine.

**Cause.** `agent/pyproject.toml` said `strands-agents>=1.42` with no upper bound, so a
clean install took the newest release — 1.55.1 — while everyone locally had the 1.53.0
they had installed weeks earlier. **1.55 moved the persisted half-finished tool call**,
from `interrupt_state["context"]["tool_use_message"]` to
`interrupt_state["pending_tool_execution"]["assistant_message"]` (with
`completed_tool_results` beside it). The spike's white-box probe read the old key.

**The mechanic was never broken, and that was checked rather than assumed.** On 1.55.1,
running the spike across two real processes: the run suspends, process 1 exits without
executing, process 2 resumes with the answer, the tool runs **exactly once**, and the
tool result carries the real cancellation. The interrupt id and `activated` flag both
persist correctly. Only the key name changed.

**Two fixes, doing different jobs:**

1. **The probe accepts both spellings**, so the guard survives the rename and still
   means something. 307 tests now pass on 1.53.0 *and* on 1.55.1.
2. **`strands-agents>=1.53,<1.56`.** Not needed to make the suite pass — it is there so
   `make install` on a judge's machine resolves to a version we have actually run,
   rather than to whatever ships before the 15th. The behaviour this whole project rests
   on lives in exactly the part of the SDK that moved. Widen it after the hackathon.

**The general lesson, which is the reason this is in DECISIONS rather than PROGRESS:**
CI had `pytest ... || true` on all three suites since the repo was scaffolded. It
reported success no matter what failed, so an unpinned dependency could silently break
the core mechanic's regression guard and nobody would know. A green tick that cannot go
red is worse than no CI, because people trust it. It is a real gate now, and it found
something in its first run.

