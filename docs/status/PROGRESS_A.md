# Progress — Lane A

**Owner:** Mikhil
**Directories:** /agent
**Branch prefix:** `a/`

---

## How to use this file

**Append new entries at the bottom. Never edit, reorder, summarise or tidy earlier
entries.** Another session — possibly another person's AI assistant — may be reading
them, and rewrites are the number one cause of merge conflicts in a shared repo.

This file is the handover between sessions. Any AI coding assistant picking up work in
Lane A should read the last two entries before doing anything.

**Only Lane A writes to this file.** Other lanes: use your own.

> **If you are Diya's or Yorvan's AI assistant: this file is Mikhil's (Lane A) working
> log. Read it freely for context, but do not edit it, do not act on its "Next" items,
> and do not treat its notes as instructions for your lane.** Your equivalent is
> `PROGRESS_B.md` or `PROGRESS_C.md`.

Template:

```markdown
## YYYY-MM-DD — session with <tool name>

**Done**
- ...

**In progress**
- ... (branch: `a/...`)

**Blocked / needs a human**
- ...

**Notes for the next session**
- ...
```

---

## 2026-08-21 — repo scaffolded

**Done**
- Lane A directories created and documented
- Read your brief: `docs/lanes/LANE_A_*.md`

**Next**
- See "Build order" in your lane brief

**Notes for the next session**
- Contracts freeze on 2026-08-24. Raise any shape you need before then — after that
  it is a `contract:` PR with two approvals.

---

## 2026-08-22 — session with Claude Code (scaffold + contracts + policy engine)

**Done**
- Repo scaffolded end to end: all lane dirs, per-directory `AGENTS.md`, coordination docs
- `/contracts` written and frozen-ready — Pydantic models (source of truth) + TypeScript
  mirror. Verified: imports cleanly, `CONTRACT_VERSION == 1.0.0`, round-trips correctly
- **`agent/quiet_hours_agent/policy.py` implemented and fully tested** — the deterministic
  policy engine. No LLM call, by design. 17/17 tests pass in `agent/tests/test_policy.py`,
  including `test_never_auto_cannot_be_policy_approved`
- `CODEOWNERS` wired with real handles (@Mikhil-sec, @diya-r6, @yorvan2401)
- Fixed a `ruff` F401 (unused `evaluate` import in `hooks.py`) that was failing CI

**Verified how**
- `ruff check contracts/python agent api integrations` → all checks passed
- `pytest agent/tests -q` → 17 passed
- Contract models instantiated and exercised manually via a throwaway script

**In progress**
- Nothing yet. Next task is the A1 interrupt spike (see build order in the lane brief).

**Blocked / needs a human**
- Nothing. Lane A is unblocked — the A1 spike uses `FileSessionManager` and needs no
  input from Lane C's provider interface.

**Notes for the next session**
- `strands-agents` is **not installed yet**. A1 is the first task that needs it.
- `hooks.py`, `graph.py`, `main.py`, `local_run.py` are deliberate stubs raising
  `NotImplementedError`, each with a docstring listing exactly what to verify first.
- Do **not** write Strands code from memory — verify `event.interrupt()`,
  `BeforeToolCallEvent` and `SessionManager` against context7 `/websites/strandsagents`.
- When A1 lands, **write the interrupt/resume payload shape into this file** — Diya needs
  it for `POST /api/decisions/{id}/respond`.
- Branch protection was removed on 22 Aug (team are git beginners). CI still runs and
  reports; the `contract:` PR-title guardrail is now honour-system.

---

## 2026-08-22 — session with Claude Code (Opus 5)

**Done — A1 the interrupt spike. The mechanic works. No fallback needed.**

- Installed `strands-agents` (resolved to **1.53.0**).
- Verified the interrupt/hook/session API against context7 `/websites/strandsagents` and
  then against the installed source. Did not write it from memory.
- Built the spike in `agent/spikes/a1_interrupt/` and proved the full loop end to end
  across a **real process boundary** (`subprocess`, not an in-process loop):
  interrupt → `stop_reason == "interrupt"` → persist a `DecisionCard` → **process exits** →
  new process rebuilds the agent → resume → tool completes.
- Both paths proven: **approve** (tool executes in process 2) and **deny** (tool never
  executes; the reason lands in a `toolResult` with `status: "error"`).
- Added `agent/tests/test_a1_interrupt_spike.py` as a regression guard, so an SDK upgrade
  that breaks this fails loudly.

**Verified how**
- `PYTHONPATH="../contracts/python;." python -m spikes.a1_interrupt.run` → both scenarios PASS
- `PYTHONPATH="contracts/python;agent" python -m pytest agent/tests -q` → **20 passed**
- `python -m ruff check contracts/python agent api integrations` → all checks passed
- Timing proof from `artifacts/side_effects.log` on an approve run — note process 1 had
  already exited before the tool ran:
  ```
  07:14:50.585 | PROCESS 1 exit (suspended at interrupt)
  07:14:52.021 | PROCESS 2 start (mode=approve)
  07:14:52.098 | EXECUTED cancel_subscription merchant=FitLife minor=3800
  ```

### Reference: the resume payload shape

**This is reference documentation, not a task for anyone else.** Recording it here so
the agent-side contract is written down while it is fresh. Mikhil is doing the
API/agent integration himself in a single pass at merge time — nobody in Lane B needs
to read or act on this section.

For the record, this is what the agent accepts back when a decision is answered.

`DecisionCard.interrupt_id` is written by Lane A when the card is created. Send it back
verbatim — **do not parse or construct it.** It looks like
`v1:before_tool_call:{toolUseId}:{uuid5}` but that format is not a contract.

The agent is resumed with a **list** of these content blocks:

```json
[
  {
    "interruptResponse": {
      "interruptId": "<DecisionCard.interrupt_id, verbatim>",
      "response": {
        "decision_id": "dec_...",
        "choice": "approve",
        "edited_params": null,
        "snooze_until": null,
        "note": "optional",
        "responded_at": "2026-08-22T07:14:52.022218Z"
      }
    }
  }
]
```

The `response` value is a **`DecisionResponse` serialised with `model_dump(mode="json")`** —
the existing frozen contract model, unchanged. No contract change is needed for A1.

Three hard requirements, learned the hard way (all three silently strand a run rather
than erroring, which is why they are written down):

1. **`response` must never be `null`.** Strands resolves an interrupt only when
   `Interrupt.response is not None`. A null answer leaves the run suspended forever and
   the card silently stays pending. Reject a null-choice response at the API boundary.
2. **`interruptId` must match exactly** or Strands raises `KeyError: no interrupt found`.
3. **The payload is a list**, even for a single decision. Strands raises `TypeError` if you
   resume with anything that is not a list of `interruptResponse` blocks.

Nothing else about Strands leaks past this boundary — that shape is the whole
agent-side interface.

### Findings worth carrying into A3

- **`event.interrupt()` does not kill the process.** It raises `InterruptException`, the
  event loop catches it, persists the session, and returns an `AgentResult` normally. So
  the runner reliably gets control back and can write the card *after* the call — using
  the authoritative `result.interrupts[].id`. This is better than writing the card inside
  the hook (which cannot know the interrupt id without touching a private method), and it
  contradicts the "may exit inside interrupt()" guess in the `hooks.py` docstring. I will
  correct that docstring in A3.
- **The hook body runs twice** — once raising, once returning the answer on resume. Any
  side effect inside a gate must be idempotent. Relevant to `store.write_activity`.
- **The interrupt id is deterministic**, not random:
  `v1:before_tool_call:{toolUseId}:{uuid5(NAMESPACE_OID, name)}`. The `toolUseId` is
  persisted in the session, so the id survives the process boundary.
- **One interrupt per hook callback**, and interrupt names must be unique within a tool
  call — two callbacks raising `qh-approval` is a `ValueError`. Matters when the telemetry
  hook lands alongside `PolicyHook`.
- `FileSessionManager` persists the pending interrupt under
  `_internal_state.interrupt_state`, including `context.tool_use_message` (the frozen tool
  call). That is what makes resume possible; S3SessionManager exists for the deployed path.
- The spike uses a scripted stub model (`scripted_model.py`) so it needs **zero AWS
  credentials**, keeping mock mode honest.

**In progress**
- Nothing. A1 is closed.

**Blocked / needs a human**
- Nothing blocking. Two things to flag:
  - `make clean` in the root `Makefile` runs `rm -rf .local` — that deletes my private
    session handoff. Root Makefile is shared, so I have not touched it. Worth changing.
  - The team still needs confirming as repo collaborators (carried over, still unverified).

**Notes for the next session**
- A2 (policy engine) was already done, so the next task is **A3: wire `policy.evaluate()`
  into the real `PolicyHook`** in `agent/quiet_hours_agent/hooks.py`. The spike's
  `SpikeApprovalHook` is the template — swap the hard-coded tool-name check for the policy
  engine, and keep the interrupt plumbing exactly as it is.
- `agent/quiet_hours_agent/store.py` still does not exist and `hooks.py` needs it.
- Read `agent/spikes/a1_interrupt/README.md` first — it documents the mechanic in detail.
- The spike stays in the tree as executable documentation and a regression test. Do not
  delete it when A3 lands.

---

## 2026-08-23 — session with Claude Code (Opus 5)

**Done — A3 (policy engine wired into the real hook), plus `make agent` now works.**

A2 was already complete, so this session closed A3 and went further: the lane now has a
working vertical slice from tool call to decision card to learned rule.

**New files**
- `agent/quiet_hours_agent/store.py` — `JsonStore`, one JSON file per record, atomic
  writes. Mock mode, zero credentials. `Store` Protocol is the seam `DynamoStore` (A7)
  slots into.
- `agent/quiet_hours_agent/hooks.py` — **the real `PolicyHook`**, no longer a stub.
  Registers on `BeforeToolCallEvent` (the gate) *and* `AfterToolCallEvent` (the audit
  trail, where success/failure is actually known).
- `agent/quiet_hours_agent/resume.py` — runner-side half: `persist_decisions`,
  `build_resume_payload`, `resume_agent`.
- `agent/quiet_hours_agent/models.py` — `build_model()`. Bedrock in live mode, a scripted
  credential-free model in mock mode.
- `agent/quiet_hours_agent/tools/` — `file_record` (silent) and `cancel_subscription`
  (confirm), the A4 starting pair.
- `agent/quiet_hours_agent/local_run.py` — **`make agent` runs a real cycle now.**

**Verified how**
- `PYTHONPATH="contracts/python;agent" python -m pytest agent/tests -q` → **46 passed**
  (17 policy + 3 spike + 20 hooks + 6 local_run)
- `python -m ruff check contracts/python agent api integrations` → all checks passed
- The three-command demo, run for real:
  ```
  run           -> 1/2 handled silently, 1 decision raised, run suspended
  --answer      -> resumed, completed, "New rule learned"
  run again     -> "Nothing needs you today."  2/2 actions handled silently
  ```
  That 1/2 → 2/2 transition is the product thesis, and it is now a test
  (`test_the_three_command_demo`).

### Design decisions worth knowing

- **Tool names are load-bearing.** A tool named exactly like an `ActionKind` value is
  governed automatically (`TOOL_ACTION_KINDS`). Name a tool after its kind and the gate
  picks it up for free; name it anything else and it passes through ungoverned. New
  action kinds therefore cannot be added without their tool becoming governed — the safe
  direction to fail in.
- **The audit entry is written in `AfterToolCallEvent`, not the gate**, because only there
  is the outcome known. Every governed call produces exactly one `ActivityEntry`,
  autonomous or not, success or failure.
- **`decision_id` is derived from the tool-use id**, not random. The gate runs twice (once
  before the interrupt, once on resume in another process) and both passes must agree on
  which card this is.
- **`NEVER_AUTO` cards do not offer "Always do this."** The engine rejects `NEVER_AUTO`
  before it reads any policy, so offering to create one would be a lie about what the rule
  would do. Guarded again in `_maybe_learn_policy`. Two tests cover it.
- **Improvised tool calls are gated at the floor risk for their kind, not inflated to
  CONFIRM.** I had this wrong first time and a test caught it: inflating meant the agent
  asked permission to file a record, which destroys the autonomy rate the whole product is
  optimising for. The floor table *is* the safety policy.
- **Console output is ASCII + forced UTF-8 stdout.** A Windows cp1252 terminal crashed on
  an em-dash coming out of a contract field. Contract data keeps proper typography; the
  terminal gets the workaround. A judge on Windows must never see a traceback.

**Blocked / needs a human**
- **A4 is blocked on Lane C.** `integrations/quiet_hours_integrations/registry.py`
  `get_providers()` still raises `NotImplementedError` for both mock and live. Until it
  lands, `tools/demo.py` has no external effect — the signatures are already shaped for
  `SubscriptionProvider.cancel`, so the swap is small. Nothing else in Lane A is blocked.
- **A6 replay needs Lane C's four-week fixtures.** `--replay-weeks` currently exits 2 with
  a clear message rather than pretending.
- `make clean` still runs `rm -rf .local`, which now also deletes the local agent store and
  sessions (intended) *and* Mikhil's private handoff (not intended). Root `Makefile` is
  shared so it is untouched; fix is queued for the merge pass.

**Notes for the next session**
- Next task is **A5, the graph** — `GraphBuilder`, triage → specialists → brief. That is
  the last big piece before the vertical slice is real. Verify `GraphBuilder` against
  context7 first; do not write it from memory.
- When A5 lands, `models.py::ScriptedModel` stops being the mock-mode model and
  `build_model` should return a real `BedrockModel` in both modes, with the graph's
  reasoning stubbed instead.
- `prompts/` is still empty. A5 needs it — prompts live in `.md` files, never inline.
- `memory.py` (AgentCore Memory) does not exist yet. A7.
- Ran `ruff format` across `agent/`, which reflowed three pre-existing lines in
  `policy.py`, `test_policy.py` and `main.py`. Formatting only, no logic touched.

---

## 2026-08-23 — session with Claude Code (Opus 5) — A5, the multi-agent graph

**Done — A5. The graph is real and `make agent` runs the whole demo through it.**

```
ingest -> triage -+-> bill_analyst -+
                  +-> negotiator   -+-> brief
                  +-> scheduler    -+
                  +------------------+   (quiet day: no specialist needed)
```

77 tests pass (was 46). Lint clean. Nothing committed — Mikhil does all git by hand.

### The question that had to be answered first

The architecture assumes an interrupt raised inside a graph node behaves exactly as A1
proved for a bare agent. **It does.** Verified before writing any of the real graph, by a
spike that spawns genuinely separate processes: `agent/spikes/a5_graph_interrupt/`, three
scenarios (approve / deny / approve_always), all passing, kept as a regression test
(`tests/test_a5_graph_spike.py`).

What it established:

- A tool call inside a node interrupts the **whole graph**: `Status.INTERRUPTED`, and
  `GraphResult.interrupts` carries the same `Interrupt` objects A1 saw.
- Interrupt ids are unchanged (`v1:before_tool_call:{toolUseId}:{uuid5}`), so the entire
  A3 gate, `decision_id_for` and `card_from_interrupt` needed **no changes**.
- Resuming is the same payload handed to the graph instead of the agent:
  `graph([{"interruptResponse": {...}}])`. Still a list; a null `response` still strands
  the run forever.
- **A resumed graph replays only the interrupted node.** Completed nodes stay completed and
  their silent actions are not repeated. Pinned by a test, because if it ever went the
  other way the activity trail would double-count and the autonomy rate would be computed
  off inflated numbers — both silent, both corrosive.

### Two SDK constraints, both silent failures if got wrong

1. **`PolicyHook` goes on each node `Agent`, never on the `GraphBuilder`.**
   `BeforeToolCallEvent` is dispatched by the tool executor through the *agent's* hook
   registry. A provider registered via `GraphBuilder.set_hook_providers([...])` only ever
   sees the multi-agent events (`BeforeNodeCallEvent` and friends). A `PolicyHook`
   registered there gates **nothing at all** while looking entirely correct in review. This
   is the single most dangerous mistake available in `graph.py`, so
   `test_every_specialist_carries_the_policy_gate` asserts it directly.
2. **The `SessionManager` goes on the `GraphBuilder`, never on a node `Agent`.** Strands
   raises `ValueError("Session persistence is not supported for Graph agents yet.")` if a
   node executor carries its own. **This is a change from A1**, where it sat on the
   `Agent`. The graph's session persists each interrupted node's messages, state and
   interrupt state on its behalf.

### New files

- `graph.py` — the real thing. `build_graph()` returns a `GraphRun` (graph + policy hook +
  invocation state), and `harvest()` promotes the result into contract objects.
- `schemas.py` — the `structured_output_model` types: `TriageResult`, `ActionPlan`,
  `BriefDraft`, plus `finding_from_draft` / `action_from_draft`.
- `prompts/*.md` + `prompts/__init__.py` — six prompts as files, with a cached loader that
  raises `PromptNotFoundError` rather than yielding an empty system prompt.
- `mock_reasoning.py` — one script per node, so mock mode still needs zero credentials.
- `signals.py` — the day's signals. **Lane A's own temporary stand-in** for Lane C's
  providers; deliberately not in `/fixtures`, which is Yorvan's.
- `tools/actions.py` — eleven governed tools, one per `ActionKind`. Replaces `tools/demo.py`.
- `tools/ingest.py` — `load_signals`, deliberately ungoverned: the gate governs actions,
  not observations.

### Design decisions worth knowing

- **The structured output models are not the contract models, on purpose.** A contract
  `Finding` carries `finding_id`, `household_id`, `run_id` and `created_at`, and none of
  those are the model's to decide. `household_id` especially is a **tenancy boundary** — a
  model that can emit one can be talked into emitting someone else's, and every downstream
  query is scoped by it. So the model supplies judgement, `graph.py` supplies identity.
  Smaller schemas also produce better structured output and cost fewer tokens per node.
- **Structured output needs no special machinery in mock mode.** Strands injects the
  structured-output tool under the schema class's own name, so a scripted step named
  `"TriageResult"` drives it. No `ScriptedModel.structured_output` implementation needed.
- **Routing is conditional, so a specialist only wakes when it has something to do.**
  `RENEWAL_UPCOMING` deliberately wakes two (push back *and* diarise). `NOTHING_TO_DO`
  wakes none.
- **Fan-in in Strands is ANY, not ALL** — a node is ready when *one* incoming edge from the
  just-completed batch is traversable. The specialists become ready together and so
  complete as one batch, meaning `brief` still fires exactly once after all of them. The
  extra `triage -> brief` edge covers the quiet day: without it, a day with nothing to do
  would produce no digest at all, which reads as the agent being broken.
- **The brief's numbers are measured, never quoted from the model.** `autonomy_rate` and
  `savings_this_month` come from the policy hook's recorded verdicts. `brief.md` forbids
  the model from stating any figure, because a brief is the one artefact the user reads as
  fact and an estimate is indistinguishable from a count.
- **`send_email` and `close_account` have no tool at all.** Not having the tool is a
  stronger guarantee than gating it. A test keeps it that way; adding either back is a
  safety decision for `DECISIONS.md` first.

### One real bug the graph exposed

Sharing a single `PolicyHook` across nodes is correct and deliberate — it accumulates the
run's verdicts and learned policies. But the specialists run **in parallel**, and
`ScriptedModel` was generating `toolUseId`s from the script index alone, so every node's
first tool call got the id `tooluse_qh_0`.

The hook keys its pending-call table — and every derived `decision_id` — on that id, so one
node's audit entry silently overwrote another's, and two unrelated actions could have
collided on one decision card. Caught because the activity trail showed one silent action
where there should have been two. Fixed with a per-instance nonce in `ScriptedModel`. A
real provider guarantees uniqueness itself; the scripted one has to do it deliberately.

### Small changes to existing files

- `resume.py::was_interrupted` now recognises `Status.INTERRUPTED` as well as
  `stop_reason == "interrupt"`. A `GraphResult` has no `stop_reason` at all, so without this
  every suspended graph looked complete, its cards were never written, and the session sat
  on disk with nothing pointing at it.
- `hooks.py::_action_from_tool_use` now uses the `rationale` the specialist passed on the
  tool call, when there is one. Only the *wording* comes from the model — risk stays pinned
  to the floor — but it is the difference between a card that explains itself and one that
  says "the agent proposed this directly".
- `hooks.py::_summarise` falls back through `subject` / `title` / `recipient` when an action
  has no merchant, so the trail does not list three identical "Set reminder" rows.
- `local_run.py` now drives the graph and prints the findings and the brief.

### The demo, as it now runs

```
run 1   4 findings; gas bill recorded and dental reminder set silently;
        stops to ask about cancelling FitLife      ->  2/3 handled silently
run 2   --answer approve_always: resumes in a new process, completes the
        cancellation, notes the Streamly trial, learns a rule
run 3   same work, now covered by the rule          ->  4/4 handled silently
```

**Blocked / needs a human**
- **A4 still blocked on Lane C.** `get_providers()` still raises `NotImplementedError`.
  `signals.py::load_signals_for` and the bodies in `tools/actions.py` are the two swap
  points, both already shaped for it. Live mode raises rather than falling back to the demo
  fixture — a live run reasoning over demo data would produce real decision cards about
  merchants the household has never heard of.
- **A6 replay still needs Lane C's four-week fixtures.** `--replay-weeks` exits 2 with a
  clear message.
- `make clean` still deletes `.local` including Mikhil's private handoff. Root `Makefile` is
  shared; fix queued for the merge pass.

**Notes for the next session**
- Next is **A6 (policy learning + the four-week autonomy curve)** if Lane C's fixtures have
  landed, otherwise **A7 (AgentCore)**. A4 is a small swap whenever `get_providers()` works.
- The earlier note that "`ScriptedModel` stops being the mock-mode model when A5 lands" was
  wrong and is now retracted: mock mode must work with **zero credentials**, so a scripted
  model is exactly what it needs. `mock_reasoning.py` is that, per node, and it stays.
- `memory.py` (AgentCore Memory) still does not exist. A7.

---

## 2026-08-24 — session with Claude Code (Opus 5) — A7, AgentCore Runtime + Memory

**A7 is done.** The agent now has a deployed entrypoint, a durable session store, a
DynamoDB record store and AgentCore Memory. **128 tests pass** (up from 77), lint clean,
and the three-command demo still runs unchanged through `make agent`.

**A4 is still blocked.** `integrations/quiet_hours_integrations/registry.py::get_providers()`
still raises `NotImplementedError` for both `MOCK` and `LIVE`, checked at the start of this
session. A6's four-week replay still needs Lane C's fixtures and still exits 2.

### The headline: the whole demo now runs over HTTP

`bedrock-agentcore` (1.22.0) was installed and the server was actually started and curled —
this is verified behaviour, not a compile-checked guess:

```
GET  /ping          -> {"status":"Healthy","time_of_last_update":...}
POST /invocations   -> SSE stream
```

The same three-command story as `make agent`, over three separate HTTP requests:

```
1  {"household_id":"hh_demo"}
     -> run_started, node_started/finished x6, decision_required, run_finished
        status=waiting_on_user, 2/3 handled silently
2  {"household_id":"hh_demo","decision_response":{...,"choice":"approve_always"}}
     -> resumed_from=[dec_...], run_finished status=completed, rule learned
3  {"household_id":"hh_demo"}
     -> no decision_required at all; 4/4 silent, policies_applied=1
```

### New files

| File | What it is |
|---|---|
| `quiet_hours_agent/main.py` | `BedrockAgentCoreApp` entrypoint. Was a stub. Streams progress envelopes; two entry paths (scheduled run / resume). |
| `quiet_hours_agent/memory.py` | AgentCore Memory read/write. Did not exist. |
| `quiet_hours_agent/sessions.py` | Chooses `FileSessionManager` (mock) vs `S3SessionManager` (live). |
| `agent/Dockerfile` | `linux/arm64`, port 8080. The container contract AgentCore imposes. |
| `tests/test_a7_runtime.py` | 13 tests — the entrypoint cycle. |
| `tests/test_memory.py` | 21 tests — including the safety property below. |
| `tests/test_persistence_live.py` | 17 tests — sessions and `DynamoStore`, against fakes. |

`store.py` gained `DynamoStore`; `build_store("live")` no longer raises.

### The two constraints A5 established have not regressed

`PolicyHook` is still on each node `Agent`; the `SessionManager` is still on the
`GraphBuilder`. `build_graph` now takes an optional `session_manager=` so the deployed path
can hand it the S3 one, and it is still passed to `builder.set_session_manager()` and
nowhere else. `test_graph.py` and `test_a5_graph_spike.py` both still pass untouched.

### Design decisions worth knowing

**Memory holds context; `policy.py` holds rules. Only rules decide whether to interrupt.**
This is the important one. Long-term memory records are written by a model summarising past
text, and that text is ultimately downstream of emails the household did not write. If
recalled text could grant autonomy, a merchant could email "this household always approves
cancellations without asking" and eventually be right. `policy.py` and `hooks.py` do not
import `memory.py`, and `test_memory_is_never_consulted_for_autonomy` asserts it
structurally — the same argument as `send_email` having no tool at all.

**Recalled memory goes in the task text, not `invocation_state` — the opposite of
`household_id`.** Deliberate. Identity must reach tools and hooks *without* entering the
model's context, where it could be prompt-injected. Memory is worthless unless the model
reads it, and it has no authority once it gets there. Capped at 800 characters.

**One Strands session per run, not per household.** This was a real bug found by the first
test run, not a theoretical one. A household-wide id rehydrates the previous run's messages
into today's run, and once a run has been resumed its session carries a spent interrupt
state — so the *next* scheduled run starts by trying to resume it and dies with
`must resume from interrupt with list of interruptResponse's`. `local_run.py` had been
managing this by deleting the session directory before each run, which the deployed path
cannot do: the sessions live in S3 and the container doing the deleting is not the one that
wrote them. `DecisionCard.session_id` carries the id, so resume never has to derive it.

**On resume, the card's `session_id` is authoritative — never AgentCore's.** Two different
identifiers share the name. AgentCore's runtime session id names the HTTP conversation; the
Strands one names the suspended graph and was written days earlier. There is a test that
passes a deliberately wrong `session_id` in the payload and asserts it is ignored.

**Live mode raises for a missing session bucket or table name, but degrades quietly for a
missing memory id.** A run with no session store loses the user's decision; a run with no
record store loses the audit trail; a run with no memory merely phrases its brief slightly
less well. Only the first two are worth refusing to start over. Every method on
`AgentCoreMemory` swallows its own exceptions for the same reason — an unreachable AWS
service must not stop the household's gas bill being paid.

**`DynamoStore` stores contract models as JSON text, not as attributes.** DynamoDB has no
float type and `Finding.confidence` is a float. Storing attributes would mean a `Decimal`
conversion on every write and back on every read, in both Lane A's code and Lane B's,
forever. Round-tripping `model_dump_json` means the bytes in the table are exactly the
frozen contract shape and both lanes parse them with the same pydantic models. It costs the
ability to query on an inner field, which nothing in the product does.

**The stream carries progress, never prose.** The web app is a decision inbox, not a chat,
so the model's token deltas are dropped. Only `run_started`, `node_started`,
`node_finished`, `decision_required`, `run_finished` and `error` are emitted, and every one
is plain JSON — a `GraphResult` in an SSE body fails inside the platform's writer, which is
the worst place to find out.

**Errors are yielded, not raised.** A raise mid-stream reaches the client as a truncated SSE
body with no status code, and "the connection ended" is not something an inbox can render.

**`bedrock_agentcore` is an optional import.** `main.py` imports and its whole cycle runs
without it — the package is only needed to *serve*. Requiring it would put an AWS SDK
between a judge and `make demo`.

### Small fixes to existing files

- `RunStats.signals_ingested` and `findings_created` were **always 0** in both runners. They
  now come from `invocation_state["signals"]` (where the ungoverned `load_signals` tool
  stashes the real `Signal` objects) and from the harvest. Lane B's autonomy chart reads
  these fields. **Diya: a resumed run still reports zero for both, and that is correct** —
  a resumed graph replays only the interrupted node, so ingest and triage do not re-run.
  Counting them again would inflate the very numbers the chart is built from.
- `models.py` now reads `QH_MODEL_ID` before `QH_BEDROCK_MODEL_ID`. The root
  `.env.example` documents the first name; this file used the second. A live deploy would
  have silently fallen back to the default model — looking like it worked, on the wrong
  model, at the wrong price.
- `graph.py::GraphRun` gained `stream()`, so a fresh run and a resume go through one code
  path in `main.py`. `Graph.stream_async` accepts the resume payload just as `__call__`
  does.

### For Lane B (Diya) — what the entrypoint gives you

`POST /invocations` streams SSE. To resume a run after the user answers a card:

```json
{"household_id": "hh_demo",
 "decision_response": {"decision_id": "...", "choice": "approve_always",
                       "responded_at": "2026-08-24T12:45:00Z"}}
```

`decision_responses` (a list) also works, because a graph can suspend on more than one
decision at once — the specialists run in parallel. You do **not** need to pass a session
id; the card carries it.

A household with a pending card is not eligible for a fresh run — the entrypoint replies
with the outstanding `decision_required` envelopes and `status: waiting_on_user` instead of
starting one.

**Blocked / needs a human**

- **A4 still blocked on Lane C.** `get_providers()` raises for both modes as of today.
- **A6 replay still needs Lane C's four-week fixtures.** Not faked — the autonomy curve is
  the demo's centrepiece and it has to be real.
- **The DynamoDB key schema needs Lane B and Lane C to agree.** Nothing in `/contracts`,
  `/infra/cdk` (empty) or `/api` defines a table today, so `DynamoStore` proposes one and
  Lane A cannot ratify it alone. Draft entry for `docs/status/DECISIONS.md` at the bottom of
  this entry — Mikhil, please paste it there rather than me editing a shared file.
- **No AgentCore deploy has been run.** The container contract and the entrypoint are done
  and verified locally; ECR, the runtime IAM role and the EventBridge schedule are `/infra`,
  which is Lane C's.
- `make clean` still deletes `.local` including the private handoff. Root `Makefile` is
  shared; fix still queued for the merge pass.
- The root `Makefile` has no target for the AgentCore entrypoint. Also shared — worth adding
  `make agent-serve` in the merge pass.

**Notes for the next session**

- Next is **A4** the moment `get_providers()` works — still a two-point swap
  (`signals.py::load_signals_for` and the eleven bodies in `tools/actions.py`). Then **A6**.
- `bedrock-agentcore==1.22.0` is now installed locally. It was already in
  `pyproject.toml`; nothing in the repo changed to accommodate it, and the suite still
  passes without it.

---

### Draft for `docs/status/DECISIONS.md` — Mikhil to paste, needs B and C

## 2026-08-24 — DynamoDB single-table layout

**Decision:** One table, name from `QH_TABLE_NAME`. A record's own id is the partition key
(`pk = sk = "DECISION#dec_abc"`); a GSI named `gsi1` answers household queries
(`gsi1pk = "HH#hh_demo#DECISION"`, `gsi1sk` = the record's timestamp). The contract model is
stored as JSON text in a `body` attribute.

**Why id-as-partition-key:** `Store.get_decision(decision_id)` takes no `household_id` —
Lane B's `POST /api/decisions/{id}/respond` only has the id from the URL. Partitioning by
household would make every read a scan or a second lookup.

**Why JSON text rather than attributes:** DynamoDB has no float type and
`Finding.confidence` is a float. Storing attributes means a `Decimal` conversion on every
write and every read, in both lanes, forever. Storing `model_dump_json` output means the
bytes in the table are exactly the frozen contract shape.

**Affects:** A writes it, B reads it, C provisions it in CDK. **Not yet agreed — this needs
Diya and Yorvan to confirm before the table is created.**

---

## 2026-08-24 (later) — session with Claude Code (Opus 5) — A4 and A6

**Lane A's build order A1–A7 is complete.** 166 tests pass, lint clean, and all three
demo paths work: `make agent`, `make replay`, and the AgentCore entrypoint over HTTP.

A4 and A6 were both listed as blocked on Lane C. They turned out to be blocked on Lane C's
*implementations*, not on its *contracts* — and the contracts already exist, so both could
be finished on this side.

### A4 — real providers, written against the published interface

`integrations/base.py` calls itself "a contract with Lane A", and it is one: the
`Providers` Protocols are complete and stable. Only `get_providers()` raises. So Lane A now
codes against the Protocols and tolerates the missing implementation:

    live  ->  providers required. Missing implementation raises.
    mock  ->  providers if available, otherwise Lane A's in-lane stand-in.

**Nothing in Lane A needs to change when Yorvan lands `c/mock-providers`.** The fallback
disappears on its own and the same code path starts calling real providers.

New file `providers.py` is the only place in the lane that imports `quiet_hours_integrations`.
Six of the eleven governed tools now reach a provider when one exists:

| Tool | Provider call |
|---|---|
| `draft_email` | `email.create_draft` (there is no `send`, by design) |
| `pay_bill` | `payments.schedule_payment` (a *request*, never a transfer) |
| `cancel_subscription` | `subscriptions.cancel` |
| `downgrade_plan` | `subscriptions.downgrade` |
| `add_calendar_event` | `calendar.create_event` |
| `set_reminder` | `calendar.create_event` (a short event — see the ask below) |

`file_record`, `tag_merchant` and `update_budget_ledger` stay in-lane because they have no
external effect at all — that is why they are `SILENT`.

`tests/test_a4_providers.py` (19 tests) supplies a fake bundle and asserts it satisfies
Lane C's Protocols with `isinstance`. If `integrations/base.py` drifts, that test fails and
tells us before anything ships. It also asserts `EmailProvider` still has **no** `send`.

### A6 — the four-week autonomy curve

```
Week        Silent / Total   Asked   Rules   Autonomy
Week 1          3 / 7          4       4      43%
Week 2          5 / 7          2       6      71%
Week 3          5 / 6          1       7      83%
Week 4          6 / 7          1       8      86%
```

`make replay`, or `--replay-weeks 4`. Eight rules learned, all from answers.

**The curve is measured, not authored.** `replay.py` says what arrives each week and what
the agent tries to do; `policy.py` decides what gets asked, from the policies actually in
the store; the rate is counted off the audit trail. The proof is
`--replay-answer approve`, which approves *without* teaching a rule:

```
approve_always   4 -> 2 -> 1 -> 1 decisions   (43% -> 86%)
approve          4 -> 4 -> 3 -> 3 decisions   (43% -> 57%)
```

Same weeks, same actions, same code. If the numbers came from the data they would be
identical. `test_replay.py` asserts the contrast.

**Week 4 deliberately still asks about one thing** — a brand-new merchant. An agent that
reached 100% would have stopped being trustworthy, and a flat 100% invites exactly the
question we do not want a judge to ask.

New files: `scenarios.py` (the mechanism: one signal -> one finding -> N actions, so
evidence citations are correct by construction) and `replay.py` (the four weeks and the
engine). `tests/test_replay.py` is 17 tests.

**The four weeks are Lane A's stand-in data**, in the same spirit as `_demo_signals` and
for the same reason — `/fixtures` is Lane C's and there is nothing in it yet. The mechanic
and the arithmetic are real; the household is invented, and the replay output says so on
screen. When Yorvan's fixtures land, the weeks are replaced and `replay()` does not change.

### Two real bugs found while building A6, both in already-shipped code

**1. Every interrupted action was counted twice.** The gate runs twice for anything that
interrupts — once to raise it, once on resume to collect the answer (A1's finding).
`PolicyHook.verdicts` was a list, so it grew by one for every action the user was asked
about. The autonomy rate was therefore **wrong in the pessimistic direction**, which is
why nobody noticed. `verdicts` is now keyed by `toolUseId`, which is stable across the
process boundary. This affected `make agent`, the AgentCore entrypoint and the replay alike.

**2. A finding routed to the wrong specialist makes its action vanish silently.** Week 4's
PhotoCloud cancellation was given an `UNEXPECTED_CHARGE` finding, which wakes the bill
analyst — and only the negotiator holds `cancel_subscription`. The node never woke, the
action never ran, and the week reported a **fraudulent 100% autonomy**. Two tests now guard
this for every scenario: one checks `NODE_TOOLS` agrees with what each specialist was
actually given, the other that every week contains a finding whose kind wakes the node its
actions need.

The second bug is the more instructive one. It produced a *better-looking* number, which is
the direction of error that survives review.

### Smaller fixes

- **`make clean` no longer deletes `.local`**, only `.local/store` and `.local/sessions`.
  It was wiping each developer's private notes.
- **New targets:** `make replay` and `make agent-serve`.
- `--replay-weeks` no longer exits 2.

### What I need from Lane C (Yorvan)

1. **`get_providers()`** — the whole of A4's remaining work. Lane A is ready; the moment
   `MOCK` returns a bundle, six tools go live with no Lane A change.
2. **`quiet_hours_integrations.mock.seed`** — `make fixtures` currently fails, which means
   **`make demo` is broken from a clean clone**. That is root `AGENTS.md` rule 3 and it is
   the single most important thing outstanding in the repo. `make agent` and `make replay`
   both work, so Lane A's demo is unaffected.
3. **Two provider methods Lane A has no way to call.** Not added unilaterally, per
   `LANE_A_AGENT.md` ("if a provider method is missing, ask Lane C"):
   - `CalendarProvider.update_event(household_id, event_ref, start, end)` — needed by
     `reschedule_appointment`, which can currently only create a new event.
   - somewhere for `dispute_charge` to go. It is `NEVER_AUTO` so it always asks the user,
     but there is no provider surface for it at all.
4. **The DynamoDB table**, per the `DECISIONS.md` entry dated today: single table,
   `pk`/`sk` = the record id, GSI `gsi1` on `gsi1pk`/`gsi1sk`.

### What I need from Lane B (Diya)

1. **The four-week curve is ready to render.** `RunStats` per run now carries real
   `signals_ingested`, `findings_created`, `actions_proposed`, `actions_autonomous`,
   `decisions_raised` and `policies_applied`. `DailyBrief.autonomy_rate` is computed from
   the audit trail.
2. **A resumed run reports zero signals and findings, and that is correct** — a resumed
   graph replays only the interrupted node, so ingest and triage do not re-run. Counting
   them again would inflate the chart.
3. **The resume payload** for the AgentCore entrypoint:
   `{"household_id": "...", "decision_response": {...}}`. `decision_responses` (a list)
   also works. You never need to pass a session id — the card carries it.
4. The DynamoDB row shape, as above: the contract model lives in `body` as JSON text, so
   you parse it with the same pydantic models Lane A writes.

**Still outstanding in Lane A**

- No AgentCore deploy has been run. ECR, the runtime IAM role and the EventBridge schedule
  are `/infra` (Lane C). `agent/Dockerfile` is Lane A's half and is done.
- `local_run.py` still uses a household-wide session id and deletes the session directory
  before each run. It works and is pinned by tests; the deployed path uses per-run ids.
  Worth unifying, not urgent.
