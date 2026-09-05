# Progress — Lane C

**Owner:** Yorvan
**Directories:** /integrations, /fixtures, /infra
**Branch prefix:** `c/`

---

## How to use this file

**Append new entries at the bottom. Never edit, reorder, summarise or tidy earlier
entries.** Another session — possibly another person's AI assistant — may be reading
them, and rewrites are the number one cause of merge conflicts in a shared repo.

This file is the handover between sessions. Any AI coding assistant picking up work in
Lane C should read the last two entries before doing anything.

**Only Lane C writes to this file.** Other lanes: use your own.

Template:

```markdown
## YYYY-MM-DD — session with <tool name>

**Done**
- ...

**In progress**
- ... (branch: `c/...`)

**Blocked / needs a human**
- ...

**Notes for the next session**
- ...
```

---

## 2026-08-21 — repo scaffolded

**Done**
- Lane C directories created and documented
- Read your brief: `docs/lanes/LANE_C_*.md`

**Next**
- See "Build order" in your lane brief

**Notes for the next session**
- Contracts freeze on 2026-08-24. Raise any shape you need before then — after that
  it is a `contract:` PR with two approvals.

---

## 2026-08-26 — session with Claude (web), onboarding + AWS setup

Yorvan joined the project today. This session was reconnaissance and account setup, not
code. Nothing in `/integrations`, `/fixtures` or `/infra` was modified.

**Done**

- Read the repo end to end: `AI_AGENT_PROTOCOL.md`, `LANE_C_INTEGRATIONS.md`, all three
  lane `AGENTS.md` files, the frozen contracts (`enums.py`, `models.py`), `base.py`, Lane
  A's `providers.py` / `signals.py` / `tools/actions.py`, the current fixture files,
  `CONTRACTS.md`, `ARCHITECTURE.md`, `DEMO_SCRIPT.md`, `infra/DEPLOY.md`, `.mcp.json`,
  CODEOWNERS and the CI workflow.
- Branch renamed `yorvan` -> `c/mock-providers` so lane inference from the branch prefix
  works.
- **AWS account created and is the project's deployment account.**
  - Account name `quiet-hours`, ID on file with Yorvan (not recorded here — public repo).
  - Free plan, $100 credits, 185 days remaining.
  - Root MFA enabled.
  - IAM user `Yorvan` with `AdministratorAccess`. Access keys created and stored locally.
  - Budget alarm `quiet-hours-guardrail`: $20/month, alert at 80% actual.
  - Region for all resources: **us-east-1**, matching `.mcp.json`.
- AWS Builder ID created: `yorvan2401` (GitHub-linked). Required at submission.
- Anthropic use case details submitted in Bedrock (the gate for first-time Claude access).

**Blocked / needs a human**

- **Fixtures shape — needs Mikhil's decision. This gates `c/mock-providers`.**
  The nine files in `fixtures/README.md` are two different kinds of artifact. Five are raw
  inputs (`household`, `inbox/`, `transactions`, `calendar`, `merchant_history`) and are
  clearly Lane C's to author. Four are *derived* (`decisions`, `activity`, `policies`,
  `runs`) — they are outputs of an agent run, carrying real `interrupt_id`s, `session_id`s
  and evidence citing specific signal IDs. Lane C cannot author those honestly; the current
  `decisions.json` shows the seam, with `"signal_id": "unbacked"` left by Lane A's stopgap
  exporter. `runs.json` is the sharper case: the 43%->86% autonomy curve is the headline
  chart, and hand-authoring it turns a measurement into a claim.
  Proposal sent to Mikhil: **two stages.** Lane C's seeder writes the five raw files; Lane
  A's `export_fixtures` stays permanently in the chain and derives the other four by running
  the agent over that data. Needs his sign-off because it changes `make fixtures` in the
  shared root Makefile and revises his DECISIONS entry of 2026-08-24, which frames the
  exporter as temporary rather than as stage two.
- **$50 Devpost AWS credit** — request submitted, redemption failed with "Something went
  wrong while redeeming your credit" (AWS-side; their error page rendered an unfilled
  `{link}` placeholder). Retry needed. Deadline 11 September 2026, 12pm PT, while supplies
  last.
- **Bedrock invocation not yet verified.** Playground returns
  `ValidationException: Operation not allowed` even with the inference profile selected.
  Most likely the Anthropic use case submission is still propagating. Bedrock -> Model access
  is retired as a page, so there is no status to check. Nothing before 31 August depends on
  this — mock mode uses Lane A's scripted fake model with zero credentials.
- **Local AWS CLI is blocked on this machine.** Windows Smart App Control refuses to load
  `_awscrt`: `ImportError: DLL load failed ... An Application Control policy has blocked
  this file.` Reproduced with both the winget install and the official MSI, so it is the
  policy, not the installer. Smart App Control cannot be re-enabled once disabled, so that
  route was rejected. Options when `cdk deploy` / `agentcore deploy` are needed (Phase 2,
  1 Sept earliest): **CloudShell** (browser terminal, preauthenticated, CLI preinstalled) or
  **WSL** (Linux binaries, policy does not apply). Not blocking anything before then.

**Notes for the next session**

- **`QH_MODEL_ID` must be an inference profile ID, not a base model ID.** Sonnet 4.5's base
  ID is `anthropic.claude-sonnet-4-5-20250929-v1:0`, but the Bedrock console states the
  model "can only be used through an inference profile". Confirmed empirically — invoking
  the base ID returns `ValidationException: Operation not allowed`. Correct value:
  `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (routes across us-east-1, us-east-2,
  us-west-2). Passed to Mikhil; this is Lane A config.
- **Submission deadline discrepancy — raised with Mikhil, docs not in Lane C.** Devpost says
  **14 September 2026, 5:00pm PDT**. `AGENTS.md`, `ROADMAP.md` and `SUBMISSION_CHECKLIST.md`
  all say 15 September, and the checklist instructs submitting on the *morning* of the 15th.
  For a UK-based team that is roughly seven hours after the deadline closes.
- **Mock providers and fixtures must land in the same branch.** Lane A's `providers.py`
  falls back to its in-lane `_demo_signals` only while `get_providers(MOCK)` raises. The
  moment it returns a bundle the fallback disappears silently — no error either way. Landing
  providers before rich fixtures would quietly make the demo worse.
- **Exact provider call surface Lane A depends on** (read from `signals.py::_from_providers`
  and `tools/actions.py`), so mock implementations satisfy it without guesswork:
  `email.fetch_since(household_id, since)`, `transactions.fetch_since(household_id, since)`,
  `calendar.fetch_between(household_id, now, now + 14d)`, `calendar.create_event(...)`,
  `email.create_draft(household_id, recipient, subject, body)`,
  `payments.schedule_payment(...)`, `subscriptions.cancel(household_id, merchant, reason)`,
  `subscriptions.downgrade(household_id, merchant, to_plan)`.
- **`base.py` is effectively frozen.** Lane A's `test_a4_providers.py` asserts the Protocols
  with `isinstance` (19 tests). Changing a signature breaks their suite silently. Announce in
  `DECISIONS.md` before touching it. Two additions Lane A has asked for remain outstanding:
  `CalendarProvider.update_event`, and a provider surface for `dispute_charge`.
- **Build order status:** step 1 (`c/provider-interface`) is already **done** — `base.py` is
  complete and merged. Next is step 2 (`c/mock-providers`), combined with step 3
  (`c/fixtures-full`) per the note above.
- **Not started and unowned by anyone else:** `docs/assets/architecture.png` does not exist,
  and the README links to it. It is a hard submission requirement and is on the never-cut
  list.
- **`infra/DEPLOY.md` contains an unverified claim** — "New AWS accounts get up to $200 in
  AgentCore free-tier credits". What is verifiable is the general AWS free-tier credit ($100
  at signup, up to $100 more via onboarding activities), usable across services. Fix when
  doing infra work; it is a Lane C file.
- **Do not commit credentials.** CI greps for AKIA-prefixed strings and private key headers.
  AWS keys belong in `~/.aws/credentials` via `aws configure`, never in the repo or `.env`.

---

## 2026-08-26 — session with Claude Code, `c/mock-providers`

**Done**

- Implemented `get_providers(ProviderMode.MOCK)` end to end: `registry.py`, and five mock
  provider classes under `integrations/quiet_hours_integrations/mock/` (`email.py`,
  `transactions.py`, `calendar.py`, `payments.py`, `subscriptions.py`) plus a shared loader,
  `mock/_fixtures.py`. `base.py` was not touched — `update_event` and `dispute_charge` both
  still need a `DECISIONS.md` entry first, per the last session's note.
- Mock providers read the five raw fixture files named in `fixtures/README.md`
  (`household.json`, `inbox/*.json`, `transactions.json`, `calendar.json`,
  `merchant_history.json`). None of the seeder's actual fixture data was written — only
  `household.json` exists today (a byproduct of Lane A's `export_fixtures` fallback). The
  four other raw files still do not exist. This is deliberate: Mikhil has not signed off on
  the fixtures-shape question yet, so authoring real fixture data was explicitly out of
  scope this session. The exact JSON shape each loader expects is documented in the
  docstrings of `mock/_fixtures.py` and in the fixture builders in `integrations/tests/conftest.py`
  — worth folding into `fixtures/README.md` once the shape question is settled, so the seeder
  (whoever ends up writing it) has one place to read it from.
- 27 tests in `integrations/tests/` (`test_mock_providers.py`, `test_registry.py`), covering:
  each provider satisfies `base.py`'s Protocols via `isinstance`; each of the five raw files
  fails with a clear `FixturesNotFoundError` (not a bare traceback) when missing; correct
  reads for email (`fetch_since`, `create_draft` never sends, `get_thread` by `thread_id`),
  transactions (`fetch_since`, `merchant_history` filtered by merchant and recency),
  calendar (`fetch_between`, `find_free_slots` around busy windows, `create_event` mutating
  only in-memory state, never `calendar.json`), payments (schedule/cancel, in-memory ledger,
  no fixture file), subscriptions (cancel/downgrade, in-memory ledger, no fixture file); and
  an unknown `household_id` raising `UnknownHouseholdError` rather than returning nothing.
  All pass: `cd integrations && pytest -q` → `27 passed`.
- **Found and fixed a real regression before it shipped, not after.** My first pass had each
  provider load its own fixture file lazily, on first read — clean per-call errors, but it
  meant `get_providers(MOCK)` itself *succeeded* the moment any fixtures existed at all, even
  a half-empty directory. I checked this against Lane A's `providers.py`, which only falls
  back to its in-lane `_demo_signals` while `get_providers(MOCK)` *raises* — the exact seam
  flagged in the previous entry below ("Mock providers and fixtures must land in the same
  branch"). With lazy-only loading, `_build()` got a real bundle back, so Lane A's fallback
  silently stopped firing, and `load_signals_for` returned an *empty* day instead of the rich
  4-signal demo stand-in — confirmed by running `load_signals_for` directly. Fixed by adding
  `require_fixture_set()` in `mock/_fixtures.py`, called once by `build_mock_providers` before
  any provider is handed back: it eagerly checks all five raw files/dirs exist and raises
  immediately if not. Individual provider classes still read lazily per-call (so unit tests
  can exercise one provider without seeding all five files), but `get_providers(MOCK)` now
  fails at build time on a partial fixture set, exactly like it does today. Re-verified after
  the fix: `providers_module.get_providers('mock')` returns `None`, and
  `load_signals_for(...)` returns the 4-signal demo stand-in again — the pre-existing
  behaviour is unchanged until real fixtures land.
- Ran the full cross-lane check, not just my own tests: Lane A's suite (`cd agent && pytest -q`)
  — **174 passed**, unchanged, including `test_a4_providers.py`. `ruff check` clean on
  everything touched. `make fixtures`'s first branch (`quiet_hours_integrations.mock.seed`)
  still declines with its existing message, so the Makefile still falls through to Lane A's
  exporter — `make demo`'s fixtures step is unaffected.
- Environment note: no venv existed in this repo yet. Created one at `<repo root>/.venv`
  (already gitignored) and installed `contracts/python`, `integrations[dev]`, `agent[dev]`
  editable into it to run both lanes' test suites. System Python is 3.14; both packages
  declare `>=3.11` and installed and ran cleanly.

**Not done / explicitly out of scope this session**

- No fixture data was written (`inbox/`, `transactions.json`, `calendar.json`,
  `merchant_history.json` still do not exist). That is `c/fixtures-full`, gated on Mikhil's
  fixtures-shape decision, per the previous entry.
- `api`/`web` were not touched or verified against these providers (out of lane; Lane B
  develops against `fixtures_server.py`, not these providers, per `AI_AGENT_PROTOCOL.md` §6).

**Blocked / needs a human**

- Fixtures-shape question is still open with Mikhil (see previous entry) — unchanged by this
  session, just re-confirming it still gates `c/fixtures-full`.

**Notes for the next session**

- The five raw fixture shapes this session's loaders expect are, in short: `household.json`
  is exactly the `Household` contract model; `inbox/` is one file per email with
  `signal_id`, `occurred_at`, `subject`, `body`, optional `merchant`/`amount`
  (`{amount_minor, currency}`)/`source`/`thread_id`; `transactions.json` is a flat list of the
  same per-record shape; `calendar.json` is a flat list with an optional `end_at` (defaults to
  a 30-minute slot); `merchant_history.json` is a dict keyed by merchant name to a list of the
  same per-record shape. Full examples: `integrations/tests/conftest.py`. Whoever writes
  `c/fixtures-full` should treat that file as the spec, not just the test data.
  `merchant_history.json`, `payments`, and `subscriptions` have no fixture file — schedule/
  cancel/downgrade are pure in-memory ledgers per provider instance, since nothing needs to
  seed them; the receipt only exists because a run acted this session.
  Mock providers now validate `household_id` against `household.json` and raise
  `UnknownHouseholdError` on a mismatch — deliberate, since the fixtures cover exactly one
  household and a mismatch is almost certainly a caller bug, not a real lookup miss.

---

## 2026-08-26 — session with Claude Code, `merchant_history` reference date + design record

**Done**

- **Fixed `MockTransactionProvider.merchant_history`'s recency cutoff.** It computed
  `datetime.now(UTC) - timedelta(days=30 * months)`, anchored to wall-clock now rather than
  the fixture world's reference date — same failure shape as the fallback regression fixed
  earlier this session: no error, just thinner evidence behind a card as real time passes
  between when the fixtures are written and when they're read.
  - Added `DEFAULT_AS_OF = datetime(2026, 8, 26, tzinfo=UTC)` to `mock/_fixtures.py` — one
    constant, documented as the value the seeder's future `--as-of` flag will also default to,
    so a reader and a fresh re-seed agree.
  - `MockTransactionProvider.__init__` now takes `as_of: datetime = DEFAULT_AS_OF` and uses
    `self._as_of` (not `now()`) as the cutoff anchor. Threaded through
    `build_mock_providers(fixtures_dir, as_of=DEFAULT_AS_OF)` and
    `get_providers(mode, *, fixtures_dir=None, as_of=DEFAULT_AS_OF)` so it's overridable
    end-to-end without changing any existing caller — Lane A's `providers.py` calls
    `get_providers(mode)` with no kwargs and gets the default, unchanged.
  - **Design choice: constructor argument, not `household.json`.** `Household` is a frozen
    contract model with no reference-date field, and its `created_at` means something
    different (when the household was onboarded, not "the fixture world's now") — bending it
    to double as the as-of would be a contract change for a concern that's really internal to
    fixture-authoring, not something Lanes A or B need. A constructor default costs nothing
    outside `/integrations` and matches the existing pattern (`fixtures_dir` is already a
    construction-time setting that isn't itself fixture data).
  - Added `test_merchant_history_cutoff_is_pinned_to_a_fixed_as_of_not_wall_clock_now` in
    `integrations/tests/test_mock_providers.py`: with `as_of=2026-08-26` and the 12-month
    default, places one entry at `2025-08-30T23:59:59Z` (excluded) and one at
    `2025-08-31T00:00:00Z` (included) and asserts exactly the second comes back — pins the
    cutoff date itself, not just "some filtering happens."
  - Verified: `cd integrations && pytest -q` → **28 passed**. `ruff check` clean (one
    auto-fixed import-sort nit, no logic change). Re-ran Lane A's suite after touching
    `registry.py`/`mock/__init__.py` — **174 passed**, unchanged.

- **Moved the fixture design record from `fixtures/design.md` to
  `docs/lanes/LANE_C_FIXTURE_DESIGN.md`**, with Yorvan's go-ahead. `fixtures/` is documented
  and treated throughout the repo as data (what the seeder writes, what Lanes A/B read); this
  is a dated design memo with rationale and a test list, which fits the existing
  `docs/lanes/LANE_<X>_<TOPIC>.md` pattern better. It was untracked, so a plain filesystem
  move, not `git mv`. Added a one-line pointer from `fixtures/README.md` to it, just above
  "The narrative these must produce", so a reader of the data directory finds the "why"
  without the design memo itself living among the JSON. The decisions themselves, so they
  survive regardless of where the file lives:

  - **Reference date:** the seeder will take `--as-of`, defaulting to the same
    `2026-08-26` constant now in `mock/_fixtures.py`. Reproducible by default; bump the
    constant to refresh before submission.
  - **Four-week calendar:** household created Mon 20 Jul 2026 (already in `household.json`)
    — twelve months of bank history imports on connection, giving the priors a legitimate
    origin. Weeks are Monday-start aggregation buckets only (the agent runs daily): Week 1
    Mon 27 Jul–Sun 2 Aug, Week 2 Mon 3–Sun 9 Aug, Week 3 Mon 10–Sun 16 Aug, Week 4 Mon 17–Sun
    23 Aug. As-of is Wed 26 Aug — a deliberate three-day gap after week 4 closes, so week 4's
    decision card has been sitting for a few days rather than looking freshly raised.
  - **FitLife resolution** (supersedes the lane brief's "eleven charges since March", which is
    internally inconsistent — eleven monthly charges implies a September 2025 last visit, not
    March): last visit **14 March 2025**; charges April 2025–August 2026 inclusive total **17
    records, £646**. Inside the provider's 12-month window (cutoff 2025-08-31, matching the
    pinned test above): **12 records, £456** — first 2025-09-03, last 2026-08-03. The £456
    figure is also the annual renewal amount due 1 September 2026 — deliberate coincidence, so
    the card can say the same number twice with two meanings ("renews at £456 for the year" /
    "you've paid £456 over the last twelve months") with no arithmetic asked of the viewer. The
    five pre-window records stay in the file (true, reward anyone who widens the window) but
    nothing on the card depends on them.
  - **Exact-string-match invariant:** `MockTransactionProvider.merchant_history` looks up
    `history.get(merchant, [])` — a plain dict lookup on an exact string, no normalisation. If
    `transactions.json` says `"British Gas"` and `merchant_history.json` says
    `"British Gas Ltd"`, the lookup silently returns `[]`: BillAnalyst gets no prior, the
    finding doesn't fire, and nothing errors. The seeder must derive both files from one
    merchant table rather than typing the name twice, and should carry a test asserting every
    distinct merchant in `transactions.json` has a matching key in `merchant_history.json`.

**Not done**

- No fixture data written — still explicitly out of scope pending Mikhil's fixtures-shape
  decision, unchanged from the previous entry.

**Blocked / needs a human**

- Fixtures-shape question with Mikhil is still open, unchanged.

**Notes for the next session**

- **`docs/lanes/` write-scope question, resolved.** `docs/lanes/LANE_C_FIXTURE_DESIGN.md` was
  created this session, but `docs/lanes/` is not in Lane C's write scope — the protocol grants
  one specific filename, `docs/lanes/LANE_C_INTEGRATIONS.md`, not the directory, and root
  `AGENTS.md` lists `/docs` as shared with per-file CODEOWNERS. The file was placed there on
  Yorvan's instruction as lane owner, before either of us had checked the literal grant, so it
  stands by his say-so rather than by protocol. Future sessions should treat `docs/lanes/` as
  not-ours-by-default and ask before adding anything else there.
  Adding `docs/lanes/` to Lane C's scope would be a one-line change to the protocol table or
  CODEOWNERS — but `docs/AI_AGENT_PROTOCOL.md` isn't ours either, so it's a request to Mikhil,
  batched with the outstanding fixtures-shape question.

---

## 2026-08-31 — no code produced

This session investigated the Bedrock access failure and read Mikhil's fixtures-shape answer.
Nothing in `/integrations`, `/fixtures`, or `/infra` was touched, so no commit followed and
nothing was recorded at the time — reconstructed here so the timeline isn't missing a day.

**Done**

- **Bedrock invocation confirmed broken account-wide, not Anthropic-specific.** Claude
  Sonnet 4.5 via the `us.` inference profile, Claude Haiku 4.5, and Amazon Nova 2 Lite all
  returned `ValidationException: Operation not allowed`. Nova is first-party Amazon with no
  third-party model subscription involved, which rules out the Anthropic use-case submission
  as the cause and points at something account- or region-level instead. **AWS support case
  178815493800207** filed, type *Account / Other Account Issues* — awaiting response.
- **Mikhil's `FOR_YORVAN.md` received**, answering the outstanding fixtures-shape question.
  Its substance — the two-stage split approved and permanent, `c/fixtures-full` unblocked, the
  `"unbacked"` signal_id traced to a Lane A bug rather than an argument for hand-authoring, the
  `except`-seam correction, and what's still outstanding for the seeder — is summarised in the
  5 September entry below, where it was actually acted on. Noted here only that it arrived
  this day, so the timeline is complete.
- **Cross-lane review, read-only, no action taken:** Mikhil's `providers.py`/`signals.py`
  hardening (described in the 5 September entry) sits on `miks-branch`, unmerged into `main`.
  Lane B's `diya` branch is at the same commit as `main` — `web/` has no `package.json`,
  `tsconfig.json`, or Next.js config, so it cannot install or build from a clean clone. Neither
  is a Lane C fix or blocker; recorded as a status snapshot.

**Blocked / needs a human**

- AWS support case 178815493800207 — awaiting response.

---

## 2026-09-05 — session with Claude Code, `Providers.as_of` + Mikhil's `FOR_YORVAN.md`

**Done**

- **Added `Providers.as_of` to `base.py`**, at Mikhil's request (relayed in `FOR_YORVAN.md`,
  §3 — see below): keyword-only, default `None`. `None` means "use wall-clock
  `datetime.now(UTC)`" — correct for `LIVE`, which leaves it unset because a live run's "now"
  really is now. `build_mock_providers` always sets it to the real reference date
  (`mock._fixtures.DEFAULT_AS_OF`, 2026-08-26), because mock fixtures are anchored to a fixed
  point in time and a caller computing a lookback window needs to know what "now" means for
  the bundle it's holding. Documented as `bundle.as_of or datetime.now(UTC)` being the pattern
  a caller should write, never `datetime.now(UTC)` alone — the latter is what silently made a
  mock-mode lookback window read the fixtures as a quiet day once wall-clock time drifted past
  their fixed dates. Keyword-only with a default means every existing construction site
  (`mock/__init__.py`'s call to `Providers(...)`) is unaffected without changes.
- **Re-exported `FixturesNotFoundError`/`UnknownHouseholdError` from the package root**
  (`quiet_hours_integrations/__init__.py`), not from `base.py` and not by moving the
  definitions into it. Reasoning: `base.py` is the Protocol contract, meant to be
  implementation-agnostic — satisfied equally by `mock/` and (eventually) `live/`. These two
  exceptions are intrinsically about reading fixture files off disk; a live provider would
  never raise either one, it fails on credentials or API errors instead. Moving them into
  `base.py` would misrepresent them as part of the contract every implementation must satisfy,
  when only `mock/` does. Re-exporting them *from* `base.py` would have the contract import
  from one specific implementation, which is backwards — the exact inversion Mikhil's own ask
  was careful to avoid triggering. The package root already aggregates the package's public
  surface without taking a position on mock vs. live, so it can re-export an implementation's
  error types without corrupting the contract file. `FixturesNotFoundError` still subclasses
  `FileNotFoundError`, so existing structural `except FileNotFoundError` code keeps working
  unchanged alongside the new named import.
- Added `test_base_does_not_import_the_mock_package` (in `integrations/tests/test_package_exports.py`)
  to guard the dependency direction the re-export choice depends on. First cut grepped
  `inspect.getsource(base)` for the string `"mock"` and failed immediately — the module
  docstring legitimately says `` `mock/` reads from `/fixtures` `` in prose. Fixed by parsing
  the source with `ast` and walking `Import`/`ImportFrom` nodes instead, checking actual import
  targets rather than substring-matching the whole file. Worth remembering generally: a
  "this module doesn't import X" test needs to check imports, not grep text, or a docstring
  mentioning X in passing fails it for the wrong reason.
- Integrations suite: **28 → 35** (4 new in `test_base.py` for `Providers.as_of` semantics,
  3 new in `test_package_exports.py` for the re-export and the AST-based import guard). All
  pass, `ruff check` clean.
- **Lane A's suite is 174, not the 178 Yorvan expected** — checked, and it's not a regression
  on this tree: Mikhil's own 28 August fix (described below) lives on `miks-branch` and is not
  merged into `main`, so none of the four tests it presumably adds are in this working copy.
  Recording this explicitly so a future session diffing against "178" doesn't mistake 174 for
  something having broken — it hasn't; the merge just hasn't happened yet.
- **Read and processed `FOR_YORVAN.md`** (Mikhil's written answer to the fixtures-shape
  question) and moved it to `docs/status/FOR_YORVAN.md`. It was untracked, so a plain
  filesystem move. Placed there rather than `docs/lanes/` for the same reason as last entry's
  scope note — it needs to be writable by Mikhil, addressed to a specific person rather than
  either a lane brief or a binding cross-lane decision, and `docs/status/` is already where
  the repo puts exactly that category of cross-person process communication, alongside
  `DECISIONS.md` and the `PROGRESS_*.md` files.

**Mikhil's answers from `FOR_YORVAN.md`** (full text now at `docs/status/FOR_YORVAN.md` —
summarised here so the key resolutions survive even if that file is later archived):

- **Two-stage raw/derived split: approved, and permanent.** The seeder writes the five raw
  files and stops; `export_fixtures` stays as a permanent stage two, not a stand-in deleted on
  landing. Mikhil owns the root `Makefile` and `DECISIONS.md` (CODEOWNERS default), and will
  make both changes and revise the 24 Aug entry himself — **we should not draft either.**
  **`c/fixtures-full` is unblocked.**
- Two corrections that shape what the seeder should produce: (a) landing the providers alone
  doesn't move the autonomy curve onto our data — the four-week replay resolves a scripted
  scenario before it ever asks `providers.py` for a bundle, so it keeps running on Lane A's
  `scenarios.py`/`replay.py::WEEKS` until Lane A re-keys those scripts onto our signal ids
  (Mikhil's A8, needs our ids frozen first); (b) `"signal_id": "unbacked"` on every stored
  decision/action is **a Lane A bug, not evidence that hand-authoring fixtures would have been
  dishonest** — `hooks.py::_action_from_tool_use` falls through to a hard-coded placeholder
  when no `action_id` is available yet, and a hand-authored `decisions.json` would have
  **hidden** this by writing a plausible-looking id instead. Also Mikhil's to fix (also A8).
- **The `except` seam we fixed was in the right place structurally but the wrong exact
  clause.** `UnknownHouseholdError` never reaches `providers.py` at all — `require_household()`
  is called by each provider at *read* time, not by `require_fixture_set()` at *build* time, so
  the clause that actually swallows it is the per-source catch in
  `signals.py::_from_providers`, not `providers.py::_build`. Mikhil has since narrowed
  `providers.py`'s fallback to `(NotImplementedError, FileNotFoundError)` only — the two
  "Lane C isn't here yet" conditions — so any other fault (a malformed `household.json`, a
  pydantic validation failure) now propagates in both modes instead of silently downgrading to
  the stand-in; and hardened `signals.py` so all three sources failing raises
  `SignalSourcesUnavailable` rather than reading as a quiet day with a perfect autonomy score.
  This is the work that lives on `miks-branch`, unmerged — see the 174-vs-178 note above.

**Still outstanding for the seeder** (per `FOR_YORVAN.md` §4, unchanged by anything this
session did):

- **Deterministic `signal_id`s.** `sig_<merchant>_<what>` style, stable across re-seeds — not
  `new_id()`/uuid4. Mikhil's A8 re-keys `scenarios.py` onto these ids; a re-seed that
  renumbers them breaks that silently, with no test to catch it.
- **A scenario manifest** mapping the nine brief scenarios to the signal ids that carry them,
  so Mikhil can re-key against something explicit rather than reading the inbox and guessing.

**Blocked / needs a human**

- Fixtures-shape question with Mikhil is resolved (see above) — `c/fixtures-full` is
  unblocked, but not started this session.
- **AWS support case 178815493800207**, filed 31 Aug: Bedrock invocation fails account-wide.
  Amazon Nova failed too, not just the Anthropic model, so this is not specific to the
  Anthropic use-case submission — narrows the likely cause to something account- or
  region-level rather than model-access approval. Awaiting AWS's response.