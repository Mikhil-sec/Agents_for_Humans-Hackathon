# AGENTS.md — Quiet Hours

**This is the canonical instruction file for every AI coding assistant working in this repository.** Cursor, GitHub Copilot, Codex, Windsurf, Gemini CLI, Zed, Aider, Jules, Junie and Claude Code all read this file natively. `CLAUDE.md` imports it. Do not duplicate rules elsewhere — change them here.

If you are an AI assistant, **read `docs/AI_AGENT_PROTOCOL.md` before your first edit.** It contains the non-negotiable rules about which files you are allowed to touch.

---

## What we are building

**Quiet Hours** is an autonomous agent that handles the recurring administrative busywork of running a household — bills, subscriptions, renewals, price increases, free-trial conversions, appointment confirmations — and **interrupts the user only when a genuine human decision is required.**

Built for the AWS *Agents for Humans* hackathon, **Everyday Agents** track. Submission deadline: **15 September 2026.**

The product thesis, in one line:

> Most agents ask you about everything. Quiet Hours earns the right to stop asking.

Every approval the user gives teaches a policy. Over four simulated weeks the agent's interrupt rate falls from ~9 decisions/week to ~2, while the number of actions it completes silently goes up. **That trend line is the product and the demo.**

## Non-negotiable product rules

1. **The web app is not a chat interface.** It is a decision inbox. On a good day it is empty. Never add a chat box to the main surface.
2. **The agent never sends a real email or moves real money unattended.** In `live` mode it creates *drafts* and *scheduled payment requests*. See "Safety model" below.
3. **Mock mode must always work with zero credentials.** `git clone && make demo` is how a hackathon judge will evaluate us. If a change breaks that, the change is wrong.
4. **Every autonomous action is logged with its reasoning** and is visible in the activity trail. No silent unexplained behaviour.

## Repository map — who owns what

| Path | Lane | Owner | Brief |
|---|---|---|---|
| `/agent` | A | Mikhil | [LANE_A_AGENT.md](docs/lanes/LANE_A_AGENT.md) |
| `/api`, `/web` | B | Teammate B | [LANE_B_WEB.md](docs/lanes/LANE_B_WEB.md) |
| `/integrations`, `/infra`, `/fixtures` | C | Teammate C | [LANE_C_INTEGRATIONS.md](docs/lanes/LANE_C_INTEGRATIONS.md) |
| `/contracts` | **shared, frozen** | all three | [CONTRACTS.md](docs/CONTRACTS.md) |
| `/docs` | shared | see per-file CODEOWNERS | — |

Each lane directory has its own `AGENTS.md` with lane-specific rules. **The nearest `AGENTS.md` to the file you are editing wins.** If you are editing `web/app/page.tsx`, `web/AGENTS.md` governs.

## The rule that matters most

> **Only edit files inside your lane's directories.**

If your task appears to require editing another lane's code, **stop and say so** rather than editing it. The correct move is to open an issue or add a note to `docs/status/DECISIONS.md`. Cross-lane edits are the single largest source of merge pain on a three-person, three-week project.

`/contracts` is frozen after **24 August 2026**. Changing it requires a PR titled `contract: ...` with approval from two lane owners. See [CONTRACTS.md](docs/CONTRACTS.md).

## Architecture in 30 seconds

```
EventBridge cron  ->  Strands agent (AgentCore Runtime)
                        |
                        |  GraphBuilder: Ingest -> Triage -> [BillAnalyst |
                        |                Negotiator | Scheduler] -> Brief
                        |
                        |  PolicyHook on BeforeToolCallEvent:
                        |     risk <= threshold  --> execute silently
                        |     otherwise          --> event.interrupt() --> DecisionCard
                        v
                   DynamoDB  <-->  FastAPI  <-->  Next.js decision inbox
```

Full detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The interrupt mechanic is the heart of the codebase. Read [docs/lanes/LANE_A_AGENT.md](docs/lanes/LANE_A_AGENT.md) before touching anything in `/agent`, even if you are only fixing a typo in a prompt.

## Tech stack

- **Agent** — Python 3.11+, `strands-agents`, `strands-agents-tools`, `bedrock-agentcore`
- **Model** — Claude Sonnet 4.5 on Amazon Bedrock (`BedrockModel`)
- **API** — FastAPI + Pydantic v2, deployed on Lambda Web Adapter
- **Web** — Next.js 15 (App Router), TypeScript, Tailwind CSS
- **Storage** — DynamoDB (decisions, runs, policies), S3 (Strands sessions), AgentCore Memory (learned preferences)
- **AWS** — Bedrock, AgentCore Runtime + Memory + Gateway, Lambda, DynamoDB, S3, EventBridge, SES, Amplify

## Conventions

**Python** — `ruff` for lint and format, line length 100. Full type hints on anything public. `pytest`. Pydantic v2 models for every boundary. No bare `except:`.

**TypeScript** — strict mode on. No `any` in committed code. Types for shared payloads come from `contracts/typescript/` — never redeclare them locally.

**Naming** — snake_case in Python, camelCase in TypeScript. **The wire format is snake_case**; `contracts/typescript/` handles the mapping. Do not "fix" this.

**Commits** — Conventional Commits: `feat(agent): ...`, `fix(web): ...`, `docs: ...`, `contract: ...`. Scope must be your lane.

**Branches** — prefix with your lane letter: `a/policy-engine`, `b/decision-card-ui`, `c/gmail-provider`. Never commit directly to `main`.

**Secrets** — never commit any. `.env.example` files only. Real values go in AWS Secrets Manager or each developer's local `.env`.

## Safety model — read before writing any tool

Tools are classified by `RiskTier` (defined in `contracts/`):

| Tier | Meaning | Behaviour |
|---|---|---|
| `SILENT` | Reversible, no external effect | Executes without asking. Logged. |
| `NOTIFY` | External but harmless and reversible | Executes, appears in the digest. |
| `CONFIRM` | Spends money, sends a message, cancels a service | **Always interrupts** unless a learned policy explicitly permits it. |
| `NEVER_AUTO` | Irreversible or high value | **Always interrupts.** No policy can auto-approve it. |

**Any tool that spends money, sends a message on the user's behalf, or terminates a service is `CONFIRM` or `NEVER_AUTO`. There are no exceptions, and no policy may downgrade a `NEVER_AUTO` tool.** If you are adding a tool and unsure, pick the stricter tier and note it in `docs/status/DECISIONS.md`.

## Definition of done

A change is done when: tests pass, `make demo` still works from a clean clone, the lane's `AGENTS.md` is still accurate, and you have appended an entry to your own `docs/status/PROGRESS_<LANE>.md`.

## Where to log progress

Append to **your own** file only: `docs/status/PROGRESS_A.md`, `PROGRESS_B.md`, or `PROGRESS_C.md`.

Never edit another lane's progress file — that is guaranteed to cause a merge conflict. Cross-cutting decisions go in `docs/status/DECISIONS.md` as a new dated section appended at the bottom.
