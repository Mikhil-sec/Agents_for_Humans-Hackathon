# Lane B — API and Web App

**Owner:** Diya
**Directories you own:** `/api`, `/web`
**Branch prefix:** `b/`
**Progress file:** `docs/status/PROGRESS_B.md`

You own the Design score. The hackathon explicitly asks whether the project is *"a complete, coherent product experience — not just a technical proof of concept."* That judgement will be made almost entirely on what you build.

---

## Your mandate

1. A FastAPI backend exposing decisions, runs, activity and policies.
2. A Next.js **decision inbox** — the surface where the agent asks its rare questions.
3. The daily digest email.
4. The autonomy trend chart, which is the demo's headline visual.

## The single most important design rule

**This is not a chat app.** Never add a chat box to the main surface.

The product thesis is that the agent works while you are not looking. The interface should feel like an inbox that is usually empty — closer to a bank's fraud-alert screen than to ChatGPT. If a judge opens it and sees a message composer, the thesis is dead.

The best possible screenshot of this product is an empty state reading **"Nothing needs you today."** with a quiet line underneath: *"Quiet Hours handled 6 things this week and saved you £34."* Design that screen first, and make it beautiful — it is the one that communicates the whole idea.

## Screens

**`/` — Today.** Pending decision cards, or the empty state. Below the fold: what was handled silently today.

**Decision card.** The core component. Must render:

- `headline` — large
- `body` — context
- **`why_asking`** — always visible, never hidden behind a disclosure. This is what makes the agent feel accountable.
- `evidence` — collapsible "Show me why", listing excerpts
- `options` as buttons, `is_default` visually primary
- For `approve_always` / `deny_always`, render **`creates_policy_preview`** prominently — *"This will also mean: always auto-pay British Gas under £150."* The user must never grant autonomy without seeing the rule in plain English.
- `urgency_deadline` as a countdown when present

**`/activity` — the audit trail.** Everything the agent did, autonomous or not. Filter by "handled silently" vs "you decided". Each row expands to show the rationale and evidence. This screen is what makes the whole thing trustworthy.

**`/policies` — what you've granted.** Every learned policy in plain English, with how many times it has fired and a one-click revoke. Judges will look for this: it is the answer to "what if it learns the wrong thing?"

**`/insights` — the autonomy chart.** Two lines over four weeks: decisions raised (falling) and actions handled silently (rising). Plus cumulative savings. **This is the screenshot that wins the Creativity score** — make it excellent.

## API surface

Frozen alongside the contracts. Response shapes come from `contracts/typescript/index.ts`.

```
GET    /api/decisions?status=pending        Page<DecisionCard>
GET    /api/decisions/{id}                  DecisionCard
POST   /api/decisions/{id}/respond          DecisionResponse -> { run_id, status }
GET    /api/runs                            Page<Run>
GET    /api/runs/{id}                       Run
GET    /api/runs/{id}/stream                SSE — live agent progress
POST   /api/runs                            trigger a run (the demo button)
GET    /api/activity?autonomous=true        Page<ActivityEntry>
GET    /api/policies                        Page<Policy>
DELETE /api/policies/{id}                   revoke
GET    /api/brief/latest                    DailyBrief
GET    /api/health                          { status, contract_version }
```

Every response carries `contract_version`. The web app compares it against its compiled-in constant and shows a banner on a major mismatch — do not remove that check.

`POST /api/decisions/{id}/respond` is the interesting one: it persists the response, then hands the Strands `interrupt_id` back to the agent to resume the suspended session. **Treat `session_id`, `interrupt_id` and `interrupt_name` as opaque.** Echo them back exactly; never parse or construct them.

## How you avoid ever waiting for Lane A

`api/app/fixtures_server.py` serves static, contract-shaped JSON from `/fixtures`. Run it with `QH_BACKEND=fixtures` and build the entire web app against it.

Build the full UI — every screen, every state — before the agent produces a single real card. When Lane A is ready, flip `QH_BACKEND=live`. If the contract held, nothing breaks.

**Build these states explicitly**, they are easy to forget and they are where products feel unfinished: empty, loading, error, contract-mismatch, decision-expired, and offline.

## Build order

1. `b/api-skeleton` — FastAPI with every route returning fixture data. Half a day.
2. `b/decision-card` — the component, in isolation, all option types.
3. `b/today-screen` — including the empty state. Make it good.
4. `b/activity-and-policies`.
5. `b/insights-chart`.
6. `b/live-backend` — swap fixtures for DynamoDB.
7. `b/sse` — live run streaming.
8. `b/digest-email` — the SES template.
9. `b/deploy` — Amplify. Get the live demo link up early; it improves our Technical Implementation score.

## Rules specific to this lane

**Types come from `contracts/typescript/index.ts`.** Never redeclare an API payload type locally, never `any`.

**Money uses `formatMoney()` from the contracts.** `amount_minor` is an integer of minor units — never divide by 100 yourself and never do arithmetic on the result.

**Timestamps are UTC.** Convert to `Household.timezone` at render time only.

**Handle unknown enum values.** Lane A may add a `FindingKind` mid-build. Every `switch` needs a default branch that degrades gracefully rather than throwing.

**Ship the live demo link early.** It is worth real points and it gets harder to do the closer we get to the deadline.

## Boundaries

You never edit `/agent`, `/integrations`, `/infra` or `/fixtures`. If you need a new fixture scenario, ask Lane C. If you need a new field, that is a `contract:` PR — see `docs/CONTRACTS.md`.

## Design direction

Calm, dense, trustworthy. Think Monzo or Linear, not a dashboard with twelve gauges. Muted palette, generous whitespace, one accent colour reserved exclusively for "this needs you". Ship dark mode — judges will screenshot it.

The emotional target: **relief.** The user should open this and feel that something has been taken off their plate.
