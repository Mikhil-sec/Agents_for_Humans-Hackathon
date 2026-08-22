# Architecture

> This document is the written companion to the architecture diagram at `docs/assets/architecture.png`. The hackathon requires a diagram covering: user interface, the Strands agent and its agentic loop, tools and integrations, AWS services, and output. All five are labelled below.

---

## The shape of the system

```
┌─ USER SURFACES ─────────────────────────────────────────────────────────┐
│                                                                          │
│   Next.js Decision Inbox            Daily digest email (SES)             │
│   (AWS Amplify Hosting)             "Nothing needs you today"            │
│   · pending decision cards          · or 1–3 cards                       │
│   · activity trail (audit)                                               │
│   · policies you have granted                                            │
│   · autonomy trend chart                                                 │
│                                                                          │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │  REST + SSE
┌────────────────────────────────▼─────────────────────────────────────────┐
│  FastAPI  (Lambda + Lambda Web Adapter)                     [Lane B]     │
│                                                                          │
│   GET  /decisions                    list pending cards                  │
│   POST /decisions/{id}/respond       user answers → resumes the agent    │
│   GET  /runs, /runs/{id}/stream      run history, live SSE               │
│   GET  /activity                     the audit trail                     │
│   GET  /policies, DELETE /policies/{id}                                  │
│   POST /runs                         manual trigger (demo button)        │
│                                                                          │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │  invoke / resume
┌────────────────────────────────▼─────────────────────────────────────────┐
│  STRANDS AGENT — Amazon Bedrock AgentCore Runtime            [Lane A]    │
│                                                                          │
│  EventBridge cron (07:00 local) ──► BedrockAgentCoreApp @app.entrypoint  │
│                                                                          │
│  ┌── GraphBuilder ────────────────────────────────────────────────────┐  │
│  │                                                                     │  │
│  │   Ingest ──► Triage ──┬──► BillAnalyst ──┐                         │  │
│  │                       ├──► Negotiator ───┼──► Brief                │  │
│  │                       └──► Scheduler ────┘                         │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  PolicyHook : HookProvider  (on BeforeToolCallEvent)                     │
│      effective_risk = max(floor(action), agent_assessed_risk)            │
│      if a live policy permits it and tier < NEVER_AUTO:                  │
│            execute silently, write ActivityEntry(was_autonomous=True)    │
│      else:                                                               │
│            event.interrupt("qh-approval", reason=...) ──► DecisionCard   │
│                                                                          │
│  SessionManager (S3)  — an interrupted run is durable. It suspends,      │
│  the process exits, and it resumes days later when the user answers.     │
│                                                                          │
└──────┬─────────────────────────────────────────┬─────────────────────────┘
       │  tools                                  │  memory & state
┌──────▼──────────────────────────────┐  ┌───────▼──────────────────────────┐
│  TOOLS & INTEGRATIONS     [Lane C]  │  │  DATA                            │
│                                     │  │                                  │
│  Email     Gmail API / mock inbox   │  │  AgentCore Memory                │
│  Money     mock bank / Plaid sandbox│  │    learned household preferences │
│  Calendar  Google Calendar / mock   │  │                                  │
│  Search    DuckDuckGo MCP (keyless) │  │  DynamoDB                        │
│              "is this hike real?"   │  │    decisions · runs · policies   │
│  Browser   Playwright MCP           │  │    activity · merchant history   │
│              drives cancel flows    │  │                                  │
│  Send      Amazon SES (drafts only) │  │  S3                              │
│                                     │  │    Strands sessions · receipts   │
│  All behind a Provider interface    │  │                                  │
│  with mock and live implementations │  │  Amazon Bedrock                  │
│                                     │  │    Claude Sonnet 4.5             │
└─────────────────────────────────────┘  └──────────────────────────────────┘
```

## The agentic loop, concretely

Quiet Hours is not a chat agent. A run is a scheduled, unattended traversal of a graph.

**1. Ingest** — pull new signals since the last watermark from every configured provider. Emails, card transactions, calendar events. No reasoning, just collection. Output: `list[Signal]`.

**2. Triage** — the model classifies each signal against `FindingKind`, correlates related ones (the "your price is changing" email *and* the card charge that follows it are one finding), and discards noise. Output: `list[Finding]`, each with evidence.

**3. Specialists** — the graph fans out. Findings route to whichever specialist can act:

- **BillAnalyst** — compares against merchant history in DynamoDB. Is this bill normal? Is the increase above inflation? Have we been charged twice?
- **Negotiator** — drafts the cancellation, the retention pushback, the dispute letter. Uses DuckDuckGo MCP to check whether a price rise is market-wide or specific to this household.
- **Scheduler** — finds free calendar slots, drafts reschedule replies, sets reminders for anything with a deadline.

Each specialist emits `ProposedAction`s.

**4. The policy gate** — this is where the product lives. Every tool call passes through `PolicyHook`, registered on `BeforeToolCallEvent`. It computes an effective risk tier, checks the household's learned policies, and either lets the call through or calls `event.interrupt()`.

**5. Brief** — composes the digest. Usually short. "Nothing needs you today" is the goal state, not a failure.

## Why the interrupt is the interesting part

Most agent demos handle human-in-the-loop by blocking on an input prompt. That works in a terminal and is useless in real life, because a scheduled agent runs at 07:00 while you are asleep.

Strands' `event.interrupt()` combined with a durable `SessionManager` gives us something better:

1. The run reaches a decision it should not make alone.
2. It calls `event.interrupt()`. The agent returns with `stop_reason == "interrupt"`.
3. We persist a `DecisionCard`, mark the `Run` as `WAITING_ON_USER`, and **the process exits.** Nothing is held open. No polling, no cost.
4. Hours or days later the user taps "Cancel it" in the web app.
5. The API posts an `interruptResponse` back into the same `session_id`. Strands rehydrates the conversation from S3 and the tool call resumes **exactly where it stopped**, with all its context intact.

That is genuinely hard to build by hand, and it is the mechanic the hackathon brief describes: *"runs autonomously and only surfaces when there's a real decision to make."*

## How autonomy is earned

The policy engine is deliberately **not** a model. Learned autonomy must be auditable and revocable, so it is deterministic code over an explicit table.

- A policy is only ever created by an explicit user choice — `APPROVE_ALWAYS` or `DENY_ALWAYS` — or typed by hand on the policies page.
- Before the user commits, the card shows `creates_policy_preview`: *"Always auto-pay British Gas under £150."* Autonomy is never granted invisibly.
- Every policy is listed on the policies page with the count of times it fired, and can be revoked in one click.
- **No policy can auto-approve a `NEVER_AUTO` action.** This is enforced in `policy.py`, not in a prompt, because prompts can be talked out of things.

The model proposes. The policy engine decides. The user governs.

## AgentCore usage

| Component | What we use it for |
|---|---|
| **Runtime** | Hosts the agent. Session isolation, up to 8h execution, `linux/arm64`, `/invocations` + `/ping` on :8080. |
| **Memory** | Long-term household preferences across runs — merchant nicknames, tolerances, standing instructions. Distinct from Strands session state, which is per-run conversation. |
| **Gateway** | Exposes our own integration endpoints as MCP tools, so the agent talks MCP to everything rather than half MCP and half bespoke Python. |
| **Identity** | Free when routed through Runtime or Gateway. Holds the Google OAuth token in live mode. |

## Mock vs live

Everything external sits behind a provider interface in `/integrations` with two implementations.

**Mock mode is the default and must never break.** A judge runs `git clone && make demo` and gets a fully working system with a seeded inbox, a seeded transaction feed, and four weeks of simulated history — with no AWS account and no credentials. The hackathon rules require the project to install and run consistently; mock mode is how we guarantee that.

**Live mode** uses real Gmail, real calendar, real Bedrock. Even in live mode:

- Emails are created as **drafts**, never sent automatically.
- Payments produce a **scheduled payment request**, never an unattended transfer.
- `NEVER_AUTO` actions always interrupt regardless of any policy.

This is not a limitation to apologise for in the README — it is the correct design for an agent with access to someone's money, and saying so plainly is worth more with judges than a reckless demo.

## Deployment topology

| Piece | Where | Why |
|---|---|---|
| Agent | AgentCore Runtime | Strengthens the Technical Implementation score; correct home for long, interruptible runs |
| API | Lambda + Lambda Web Adapter | Same FastAPI app runs locally and deployed |
| Web | AWS Amplify Hosting | Gives us the optional live demo link, which the rules say improves scoring |
| Schedule | EventBridge cron | The agent is not something you open |
| Data | DynamoDB + S3 | Single-digit-ms reads for the inbox; S3 for session durability |
| Email | SES | The digest |
| Secrets | Secrets Manager | Never in the repo |

## Repository layout

```
/contracts      frozen shared types (Python source of truth + TS mirror)
/agent          Lane A — Strands agents, graph, tools, policy engine
/api            Lane B — FastAPI
/web            Lane B — Next.js decision inbox
/integrations   Lane C — providers (mock + live)
/fixtures       Lane C — seeded demo data
/infra          Lane C — CDK, AgentCore deploy, EventBridge, SES
/docs           this, the lane briefs, status, submission checklist
```
