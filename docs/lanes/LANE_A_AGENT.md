# Lane A — The Strands Agent

**Owner:** Mikhil
**Directories you own:** `/agent`
**Branch prefix:** `a/`
**Progress file:** `docs/status/PROGRESS_A.md`

You own the part of the project the judges will score hardest on Technical Implementation. Everything else in the repo exists to show your work off.

---

## Your mandate

Build the Strands agent that:

1. Wakes on a schedule and ingests signals through the provider interface (Lane C's).
2. Reasons about them in a multi-agent `Graph` to produce findings and proposed actions.
3. Passes every action through a **deterministic policy engine** that either executes it silently or raises a `DecisionCard` via `event.interrupt()`.
4. Survives suspension — an interrupted run must resume correctly days later.
5. Learns policies from the user's answers so the interrupt rate falls over time.

## What "done" looks like

- `make agent` runs a full cycle in mock mode with no AWS credentials.
- A run that hits an interrupt exits cleanly, leaving a resumable session on disk.
- Answering the decision resumes that exact session and completes the action.
- Replaying four weeks of fixtures shows autonomy rate climbing from ~35% to ~85%.
- The agent is deployed to AgentCore Runtime and invokable.

## Files you own

```
agent/
├── AGENTS.md                    lane rules for AI assistants
├── pyproject.toml
├── quiet_hours_agent/
│   ├── main.py                  BedrockAgentCoreApp entrypoint
│   ├── local_run.py             `make agent` — mock-mode CLI runner
│   ├── graph.py                 GraphBuilder wiring
│   ├── agents/
│   │   ├── triage.py            classifies signals into findings
│   │   ├── bill_analyst.py      history comparison, anomaly detection
│   │   ├── negotiator.py        drafts cancellations, disputes, pushback
│   │   ├── scheduler.py         calendar work, reminders
│   │   └── brief.py             composes the digest
│   ├── policy.py                THE POLICY ENGINE — deterministic, no model
│   ├── hooks.py                 PolicyHook (BeforeToolCallEvent) + telemetry
│   ├── resume.py                resuming a suspended run from a DecisionResponse
│   ├── memory.py                AgentCore Memory read/write
│   ├── store.py                 DynamoDB persistence (local JSON in mock mode)
│   ├── tools/                   @tool functions, one module per action family
│   └── prompts/                 system prompts as .md files, not inline strings
└── tests/
```

## Build order — do not reorder these

**A1. The interrupt loop, end to end, with one hard-coded action.** No graph, no model reasoning, no real tools. Prove: `Agent` with a `HookProvider` that interrupts → `stop_reason == "interrupt"` → persist a card → new process → resume with `interruptResponse` → tool completes.

This is the single highest-risk piece of the project and everything depends on it. **Do this first, in the first two days.** If the mechanic does not work the way we think, we need to know immediately, not in week three.

**A2. The policy engine.** Pure functions, no Strands, no model, heavily unit-tested. `evaluate(action, policies) -> Verdict`. Get the `NEVER_AUTO` guard right and test it explicitly.

**A3. Wire A2 into A1.** Now the interrupt fires conditionally.

**A4. Real tools** against Lane C's mock providers. Start with `file_record` (silent) and `cancel_subscription` (confirm) — one on each side of the gate.

**A5. The graph.** Triage → specialists → brief.

**A6. Policy learning.** `APPROVE_ALWAYS` creates a `Policy`. Then the four-week replay to produce the autonomy curve.

**A7. AgentCore.** Runtime deployment, then Memory.

## Strands APIs you will need

Do **not** write these from memory. Use the `context7` MCP server against `/websites/strandsagents`, or the docs at `strandsagents.com`. The SDK moves fast.

| Concept | Why you need it |
|---|---|
| `Agent`, `@tool` | The basics |
| `BedrockModel` | Claude Sonnet 4.5 on Bedrock |
| `HookProvider`, `BeforeToolCallEvent` | Where the policy gate lives |
| `event.interrupt(name, reason=...)` | Raising a decision |
| `result.stop_reason == "interrupt"`, `result.interrupts` | Detecting one |
| `interruptResponse` payload | Resuming |
| `FileSessionManager` / S3 session manager | Durability across process exits |
| `GraphBuilder` | Multi-agent orchestration |
| `invocation_state` | Passing `household_id` etc. without putting it in the prompt |
| `structured_output_model` | Getting typed `Finding` / `ProposedAction` objects out of the model |
| `agent.stream_async` | Streaming for the AgentCore entrypoint |

## Rules specific to this lane

**The policy engine must not call a model.** It is deterministic code over an explicit table. Learned autonomy has to be auditable and revocable; a model deciding whether to ask permission is exactly the thing users would not trust. Judges will notice this distinction if you make it clearly.

**No policy may auto-approve a `NEVER_AUTO` action.** Enforce it in `policy.py` with a test named `test_never_auto_cannot_be_policy_approved`. Not in a prompt — prompts can be argued with.

**Prompts live in `prompts/*.md`, not in Python string literals.** They will be iterated on constantly and they are easier to review as files.

**Every action produces an `ActivityEntry`**, autonomous or not, success or failure. The audit trail is a product promise.

**Use `structured_output_model`** rather than parsing JSON out of prose. It is more robust and it demonstrates deeper SDK knowledge.

## Boundaries

You **consume** the provider interface from `/integrations` — you do not implement it. If a provider method is missing, ask Lane C; do not add it yourself.

You **write** to storage through `agent/store.py` using contract models. Lane B reads the same records through their own code. You two never call each other's Python.

You **never** edit `/web`, `/api`, `/integrations`, `/infra` or `/fixtures`.

## Your first three tasks

1. `a/spike-interrupt` — the A1 spike. Timebox to one day. Write down in `PROGRESS_A.md` exactly how the interrupt payload is shaped, because Lane B needs it for the resume endpoint.
2. `a/policy-engine` — A2 with tests.
3. `a/graph-skeleton` — all five nodes, stub reasoning, wired end to end.

## If you get stuck

- Interrupt semantics unclear → check `strandsagents.com/docs/user-guide/concepts/interrupts` via context7 before improvising.
- AgentCore deploy failing → `aws-knowledge` MCP server. Note that the old `bedrock-agentcore-starter-toolkit` CLI is deprecated; the current tool is the AgentCore CLI (`npm install -g @aws/agentcore`).
- Blocked on another lane → you should not be. Re-read `docs/CONTRACTS.md`.
