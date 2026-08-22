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

## Before you finish

Run `pytest`. Confirm `make demo` still works. Append a dated entry to
`docs/status/PROGRESS_A.md` — append at the bottom, never rewrite earlier entries.
