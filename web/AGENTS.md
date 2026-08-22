# AGENTS.md — /web (Lane B)

Root rules: [../AGENTS.md](../AGENTS.md). Protocol: [../docs/AI_AGENT_PROTOCOL.md](../docs/AI_AGENT_PROTOCOL.md).
Full brief: [../docs/lanes/LANE_B_WEB.md](../docs/lanes/LANE_B_WEB.md) — **read it before your first edit.**

## You are in Lane B

You may edit `/web` and `/api`. **You may not edit** `/agent`, `/integrations`, `/infra`,
`/fixtures` or `/contracts`.

## The rule that defines this directory

**This is not a chat app. Never add a chat box to the main surface.**

Quiet Hours is a decision inbox that is usually empty. The best screenshot of this product
is the empty state: *"Nothing needs you today."* If it looks like a chatbot, the entire
product thesis collapses.

## Non-negotiables in this directory

1. **Types come from `contracts/typescript/index.ts`.** Never redeclare an API payload
   type locally. No `any` in committed code.
2. **Money: use `formatMoney()`.** `amount_minor` is an integer count of minor units.
   Never divide by 100 yourself, never do arithmetic on the result.
3. **Timestamps are UTC.** Convert to `Household.timezone` at render time only.
4. **Always render `DecisionCard.why_asking`.** Never behind a disclosure. It is what
   makes the agent feel accountable rather than arbitrary.
5. **Always render `creates_policy_preview`** on `approve_always` / `deny_always` options.
   The user must see the rule in plain English before granting autonomy.
6. **Every `switch` on an enum needs a default branch.** Lane A may add a `FindingKind`
   mid-build; unknown values must degrade gracefully, not throw.
7. Build the empty, loading, error, contract-mismatch, expired and offline states
   explicitly. They are where a product feels finished or doesn't.

## Design direction

Calm, dense, trustworthy — Monzo or Linear, not a dashboard with twelve gauges. Muted
palette, generous whitespace, one accent colour reserved exclusively for "this needs you".
The emotional target is **relief**.

## How to run

```bash
cd web && npm install && npm run dev
```

Point it at the fixtures API (`QH_BACKEND=fixtures` in `/api`) — you never need the agent
running to build any screen here.

## Before you finish

Run the dev server and actually open the page you changed. Use the `playwright` MCP server
to verify rather than assuming it renders. Append a dated entry to
`docs/status/PROGRESS_B.md`.
