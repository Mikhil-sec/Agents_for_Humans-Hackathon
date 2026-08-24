# AGENTS.md — /agent (Lane A)

Root rules: [../AGENTS.md](../AGENTS.md). Protocol: [../docs/AI_AGENT_PROTOCOL.md](../docs/AI_AGENT_PROTOCOL.md).
Full brief: [../docs/lanes/LANE_A_AGENT.md](../docs/lanes/LANE_A_AGENT.md) — **read it before your first edit.**

## You are in Lane A

You may edit `/agent`, `docs/lanes/LANE_A_AGENT.md` and `docs/status/PROGRESS_A.md`.

**You may not edit** `/api`, `/web`, `/integrations`, `/infra`, `/fixtures` or `/contracts`.
If the task seems to need it, stop and tell the human what needs to change and where.

## What lives here

The Strands agent: the multi-agent graph, the tools, and the policy engine that decides
whether an action executes silently or interrupts the user.

`providers.py` is the **only** place that touches `/integrations`. Live mode requires Lane
C's bundle and raises without it; mock mode falls back to the in-lane stand-in. Never add a
second import of `quiet_hours_integrations` elsewhere in the lane.

## Non-negotiables in this directory

1. **`policy.py` must never call a model.** It is deterministic code over an explicit
   policy table. Learned autonomy has to be auditable and revocable, and a prompt can be
   argued out of a safety rule where an `if` statement cannot.
2. **No policy may auto-approve a `NEVER_AUTO` action.** Enforced in `policy.py`, covered
   by a test named `test_never_auto_cannot_be_policy_approved`. Do not weaken it.
3. **Every action writes an `ActivityEntry`** — autonomous or not, success or failure.
4. **Prompts live in `prompts/*.md`**, never as inline Python strings.
5. **Use `structured_output_model`** to get typed contract objects out of the model.
   Do not hand-parse JSON from prose.
6. **An action's effective risk is `max(DEFAULT_RISK_BY_ACTION[kind], proposed_risk)`.**
   An agent may raise its own risk assessment; it may never lower it below the floor.

## Do not write Strands code from memory

The SDK moves fast. Use the `context7` MCP server against `/websites/strandsagents`, or
`strandsagents.com`. Verify before you write, especially: `GraphBuilder`,
`event.interrupt()`, `HookProvider`, `BeforeToolCallEvent`, `SessionManager`,
`invocation_state`, `structured_output_model`, `stream_async`.

For AgentCore, use the `aws-knowledge` MCP server. Note the old
`bedrock-agentcore-starter-toolkit` CLI is deprecated — the current tool is the AgentCore
CLI (`npm install -g @aws/agentcore`).

## How to run

```bash
cd agent && pip install -e ".[dev]"
QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run
pytest -q
```

Mock mode must always work with zero credentials. If your change breaks that, the change
is wrong.

The deployed entrypoint is the same cycle behind an HTTP surface, and it also runs in mock
mode with no AWS account:

```bash
QH_PROVIDER_MODE=mock python -m quiet_hours_agent.main    # serves :8080
curl -XPOST localhost:8080/invocations -H 'Content-Type: application/json'   -d '{"household_id":"hh_demo"}'
```

`main.py` and `local_run.py` are twins — same graph, same gate, same store. A change to the
cycle that only lands in one of them is a bug.

## The autonomy curve

```bash
QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run --replay-weeks 4
```

Four simulated weeks; the interrupt rate falls as the policy engine learns. **The
curve is measured, never authored.** `replay.py` says what arrives and what the agent
tries; `policy.py` decides what gets asked; the rate is counted off the audit trail.

`--replay-answer approve` answers without teaching a rule and produces a much flatter
line. That contrast is the proof, and `test_replay.py` asserts it.

If you add a week, `test_replay.py` checks two things that fail silently otherwise: every
action must be routed to a node that owns its tool, and every week must contain a finding
whose kind actually wakes that node. Get either wrong and the action never runs — the week
just looks quieter than it is.

## Two identifiers called `session_id`

`DecisionCard.session_id` is the **Strands** session: it names the suspended graph, was
written when the card was raised, and is the only thing that rehydrates the pending tool
call. AgentCore's runtime session id names the *HTTP conversation*. On resume, always read
it off the card — never off the payload or the request context.

Sessions are **one per run**, not one per household. A household-wide id rehydrates the
previous run's messages into today's run, and leaves a spent interrupt state that makes the
next run fail on resume. See `sessions.py`.

## Before you finish

Run `pytest`. Confirm `make demo` still works. Append a dated entry to
`docs/status/PROGRESS_A.md` — append at the bottom, never rewrite earlier entries.
