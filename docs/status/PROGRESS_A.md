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
