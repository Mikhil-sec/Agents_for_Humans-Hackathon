# Lane C — Integrations, Fixtures and Infrastructure

**Owner:** Yorvan
**Directories you own:** `/integrations`, `/fixtures`, `/infra`
**Branch prefix:** `c/`
**Progress file:** `docs/status/PROGRESS_C.md`

You own two things that decide whether we place: **the demo data** and **the deployment**. Neither is glamorous. Both are the difference between a good idea and a submission that scores.

---

## Your mandate

1. A provider interface with `mock` and `live` implementations for email, transactions and calendar.
2. Fixture data good enough that the agent has genuinely interesting work to do.
3. Deployment: AgentCore Runtime, Lambda, DynamoDB, S3, EventBridge, SES, Amplify.
4. The architecture diagram and the demo recording.

## Why the fixtures matter more than they look

A judge will spend about four minutes with our repo. Almost all of that is `make demo` and the video. **The fixtures are the product they experience.**

If the seeded inbox contains three boring bills, the agent has nothing interesting to say and the demo is flat. If it contains a gym membership the user forgot in March, a streaming service that quietly went up £2.50, a duplicate cloud-storage subscription, and a free trial converting in two days — the agent looks brilliant, because it *is* doing something a person would genuinely miss.

**You are writing the script that the agent performs.** Take it seriously.

### The four-week narrative

Fixtures span four simulated weeks and must produce this arc:

| Week | Decisions raised | Handled silently | The story |
|---|---|---|---|
| 1 | ~9 | ~4 | The agent is new. It asks about almost everything. |
| 2 | ~6 | ~11 | Early policies land. It stops asking about routine bills. |
| 3 | ~3 | ~19 | It handles most things. Asks only about money and messages. |
| 4 | ~2 | ~26 | Quiet. Two real decisions in a week. |

That curve is the demo's headline chart. Build the fixtures backwards from it.

### Scenarios to seed

Each of these must be discoverable from the data alone — no hints in the prompts:

- **The forgotten gym.** FitLife, £38/mo, last visited March. Eleven charges since. → `unused_subscription`, saves £456/yr.
- **The quiet price rise.** A streaming service goes £12.99 → £15.49 with a "we're updating our prices" email that buries the number. → `price_increase`.
- **The trial about to convert.** Signed up 13 days ago, converts to £24/mo in 48 hours. → `trial_converting`, with `urgency_deadline`.
- **The duplicate.** Both Dropbox and Google One at 2TB. → `duplicate_service`.
- **The double charge.** Same merchant, same amount, same day, twice. → `unexpected_charge` → `dispute_charge`, which is `NEVER_AUTO` and must always interrupt.
- **The routine bill.** Electricity, £94, arrives monthly, always the same. → `bill_due`. This is the one the agent learns to stop asking about — it is what makes the autonomy curve move.
- **The usage spike.** Water bill triples. Could be a leak. → `usage_anomaly`. Worth a decision even though no money moves, because it is a genuinely useful thing to be told.
- **The appointment.** Dentist confirmation clashing with a calendar event. → `appointment_needs_reply`.
- **Noise.** Marketing emails, newsletters, delivery notifications. The agent must correctly ignore ~60% of the inbox. Showing what it *doesn't* act on is as convincing as showing what it does.

Use plausible UK merchants and amounts. Do not use "Acme Corp" — fake-looking data makes the whole thing look like a toy.

## Files you own

```
integrations/
├── AGENTS.md
├── pyproject.toml
├── quiet_hours_integrations/
│   ├── base.py              Protocol definitions — the interface Lane A codes against
│   ├── registry.py          get_providers(mode) -> Providers
│   ├── mock/
│   │   ├── email.py         reads fixtures/inbox/
│   │   ├── transactions.py  reads fixtures/transactions.json
│   │   ├── calendar.py
│   │   └── seed.py          generates the four-week fixture set
│   └── live/
│       ├── gmail.py         Gmail API — DRAFTS ONLY, never sends
│       ├── plaid.py         Plaid sandbox (free)
│       ├── gcal.py
│       └── ses.py           the digest email
└── tests/

fixtures/
├── household.json
├── inbox/                   one .json per message
├── transactions.json
├── calendar.json
└── merchant_history.json    12 months of priors, so BillAnalyst can compare

infra/
├── cdk/                     DynamoDB, S3, Lambda, EventBridge, SES, IAM
├── agentcore/               AgentCore Runtime + Memory config
└── DEPLOY.md                runbook — must be followable by a stranger
```

## The provider interface

Defined in `integrations/quiet_hours_integrations/base.py` as `typing.Protocol` classes. **This is a contract with Lane A** — treat changes to it with the same care as `/contracts`. Lane A codes against it from day one and cannot absorb surprise changes.

Both implementations must satisfy the same tests. Write the test suite once, parametrised over `mock` and `live`; live tests skip without credentials.

## Hard safety rules

**The live Gmail provider creates drafts. It has no send path at all.** Do not implement one "for later". Absence of the code is the guarantee.

**The live payment provider creates scheduled payment requests, never unattended transfers.**

**Never commit a credential.** `.env.example` only. Real values in Secrets Manager. If you commit one by accident, rotate it immediately and say so — do not quietly force-push.

## Build order

1. `c/provider-interface` — **day one, before anything else.** Lane A is blocked on this and only this. Get `base.py` merged within 24 hours.
2. `c/mock-providers` — mock implementations plus a minimal fixture set so Lane A can run.
3. `c/fixtures-full` — the complete four-week narrative.
4. `c/infra-core` — DynamoDB, S3, IAM.
5. `c/agentcore-deploy` — with Lane A. Use the current AgentCore CLI (`npm install -g @aws/agentcore`); the old `bedrock-agentcore-starter-toolkit` is deprecated.
6. `c/live-providers` — Gmail and calendar OAuth.
7. `c/schedule-and-email` — EventBridge cron and the SES digest.
8. `c/diagram` — the architecture diagram.
9. `c/demo` — the video.

## The architecture diagram

A required deliverable. It must label: user interface, the Strands agent and its loop, tools and integrations, AWS services, and output. `docs/ARCHITECTURE.md` has the ASCII version — turn it into a clean diagram (draw.io or Excalidraw with official AWS icons), export a PNG to `docs/assets/architecture.png`, and commit the source file too.

## The demo video

Maximum five minutes. Must show the project working end to end, and must cover the problem, who it is for, and why it matters. Script in `docs/DEMO_SCRIPT.md` — follow it, and record with the mock-mode system so nothing depends on live credentials on the day.

## Boundaries

You never edit `/agent`, `/api` or `/web`. If a lane needs a new fixture scenario, they ask you — add it, do not edit their code to work around it.
