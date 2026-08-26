# Progress — Lane C

**Owner:** Yorvan
**Directories:** /integrations, /fixtures, /infra
**Branch prefix:** `c/`

---

## How to use this file

**Append new entries at the bottom. Never edit, reorder, summarise or tidy earlier
entries.** Another session — possibly another person's AI assistant — may be reading
them, and rewrites are the number one cause of merge conflicts in a shared repo.

This file is the handover between sessions. Any AI coding assistant picking up work in
Lane C should read the last two entries before doing anything.

**Only Lane C writes to this file.** Other lanes: use your own.

Template:

```markdown
## YYYY-MM-DD — session with <tool name>

**Done**
- ...

**In progress**
- ... (branch: `c/...`)

**Blocked / needs a human**
- ...

**Notes for the next session**
- ...
```

---

## 2026-08-21 — repo scaffolded

**Done**
- Lane C directories created and documented
- Read your brief: `docs/lanes/LANE_C_*.md`

**Next**
- See "Build order" in your lane brief

**Notes for the next session**
- Contracts freeze on 2026-08-24. Raise any shape you need before then — after that
  it is a `contract:` PR with two approvals.

---

## 2026-08-26 — session with Claude (web), onboarding + AWS setup

Yorvan joined the project today. This session was reconnaissance and account setup, not
code. Nothing in `/integrations`, `/fixtures` or `/infra` was modified.

**Done**

- Read the repo end to end: `AI_AGENT_PROTOCOL.md`, `LANE_C_INTEGRATIONS.md`, all three
  lane `AGENTS.md` files, the frozen contracts (`enums.py`, `models.py`), `base.py`, Lane
  A's `providers.py` / `signals.py` / `tools/actions.py`, the current fixture files,
  `CONTRACTS.md`, `ARCHITECTURE.md`, `DEMO_SCRIPT.md`, `infra/DEPLOY.md`, `.mcp.json`,
  CODEOWNERS and the CI workflow.
- Branch renamed `yorvan` -> `c/mock-providers` so lane inference from the branch prefix
  works.
- **AWS account created and is the project's deployment account.**
  - Account name `quiet-hours`, ID on file with Yorvan (not recorded here — public repo).
  - Free plan, $100 credits, 185 days remaining.
  - Root MFA enabled.
  - IAM user `Yorvan` with `AdministratorAccess`. Access keys created and stored locally.
  - Budget alarm `quiet-hours-guardrail`: $20/month, alert at 80% actual.
  - Region for all resources: **us-east-1**, matching `.mcp.json`.
- AWS Builder ID created: `yorvan2401` (GitHub-linked). Required at submission.
- Anthropic use case details submitted in Bedrock (the gate for first-time Claude access).

**Blocked / needs a human**

- **Fixtures shape — needs Mikhil's decision. This gates `c/mock-providers`.**
  The nine files in `fixtures/README.md` are two different kinds of artifact. Five are raw
  inputs (`household`, `inbox/`, `transactions`, `calendar`, `merchant_history`) and are
  clearly Lane C's to author. Four are *derived* (`decisions`, `activity`, `policies`,
  `runs`) — they are outputs of an agent run, carrying real `interrupt_id`s, `session_id`s
  and evidence citing specific signal IDs. Lane C cannot author those honestly; the current
  `decisions.json` shows the seam, with `"signal_id": "unbacked"` left by Lane A's stopgap
  exporter. `runs.json` is the sharper case: the 43%->86% autonomy curve is the headline
  chart, and hand-authoring it turns a measurement into a claim.
  Proposal sent to Mikhil: **two stages.** Lane C's seeder writes the five raw files; Lane
  A's `export_fixtures` stays permanently in the chain and derives the other four by running
  the agent over that data. Needs his sign-off because it changes `make fixtures` in the
  shared root Makefile and revises his DECISIONS entry of 2026-08-24, which frames the
  exporter as temporary rather than as stage two.
- **$50 Devpost AWS credit** — request submitted, redemption failed with "Something went
  wrong while redeeming your credit" (AWS-side; their error page rendered an unfilled
  `{link}` placeholder). Retry needed. Deadline 11 September 2026, 12pm PT, while supplies
  last.
- **Bedrock invocation not yet verified.** Playground returns
  `ValidationException: Operation not allowed` even with the inference profile selected.
  Most likely the Anthropic use case submission is still propagating. Bedrock -> Model access
  is retired as a page, so there is no status to check. Nothing before 31 August depends on
  this — mock mode uses Lane A's scripted fake model with zero credentials.
- **Local AWS CLI is blocked on this machine.** Windows Smart App Control refuses to load
  `_awscrt`: `ImportError: DLL load failed ... An Application Control policy has blocked
  this file.` Reproduced with both the winget install and the official MSI, so it is the
  policy, not the installer. Smart App Control cannot be re-enabled once disabled, so that
  route was rejected. Options when `cdk deploy` / `agentcore deploy` are needed (Phase 2,
  1 Sept earliest): **CloudShell** (browser terminal, preauthenticated, CLI preinstalled) or
  **WSL** (Linux binaries, policy does not apply). Not blocking anything before then.

**Notes for the next session**

- **`QH_MODEL_ID` must be an inference profile ID, not a base model ID.** Sonnet 4.5's base
  ID is `anthropic.claude-sonnet-4-5-20250929-v1:0`, but the Bedrock console states the
  model "can only be used through an inference profile". Confirmed empirically — invoking
  the base ID returns `ValidationException: Operation not allowed`. Correct value:
  `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (routes across us-east-1, us-east-2,
  us-west-2). Passed to Mikhil; this is Lane A config.
- **Submission deadline discrepancy — raised with Mikhil, docs not in Lane C.** Devpost says
  **14 September 2026, 5:00pm PDT**. `AGENTS.md`, `ROADMAP.md` and `SUBMISSION_CHECKLIST.md`
  all say 15 September, and the checklist instructs submitting on the *morning* of the 15th.
  For a UK-based team that is roughly seven hours after the deadline closes.
- **Mock providers and fixtures must land in the same branch.** Lane A's `providers.py`
  falls back to its in-lane `_demo_signals` only while `get_providers(MOCK)` raises. The
  moment it returns a bundle the fallback disappears silently — no error either way. Landing
  providers before rich fixtures would quietly make the demo worse.
- **Exact provider call surface Lane A depends on** (read from `signals.py::_from_providers`
  and `tools/actions.py`), so mock implementations satisfy it without guesswork:
  `email.fetch_since(household_id, since)`, `transactions.fetch_since(household_id, since)`,
  `calendar.fetch_between(household_id, now, now + 14d)`, `calendar.create_event(...)`,
  `email.create_draft(household_id, recipient, subject, body)`,
  `payments.schedule_payment(...)`, `subscriptions.cancel(household_id, merchant, reason)`,
  `subscriptions.downgrade(household_id, merchant, to_plan)`.
- **`base.py` is effectively frozen.** Lane A's `test_a4_providers.py` asserts the Protocols
  with `isinstance` (19 tests). Changing a signature breaks their suite silently. Announce in
  `DECISIONS.md` before touching it. Two additions Lane A has asked for remain outstanding:
  `CalendarProvider.update_event`, and a provider surface for `dispute_charge`.
- **Build order status:** step 1 (`c/provider-interface`) is already **done** — `base.py` is
  complete and merged. Next is step 2 (`c/mock-providers`), combined with step 3
  (`c/fixtures-full`) per the note above.
- **Not started and unowned by anyone else:** `docs/assets/architecture.png` does not exist,
  and the README links to it. It is a hard submission requirement and is on the never-cut
  list.
- **`infra/DEPLOY.md` contains an unverified claim** — "New AWS accounts get up to $200 in
  AgentCore free-tier credits". What is verifiable is the general AWS free-tier credit ($100
  at signup, up to $100 more via onboarding activities), usable across services. Fix when
  doing infra work; it is a Lane C file.
- **Do not commit credentials.** CI greps for AKIA-prefixed strings and private key headers.
  AWS keys belong in `~/.aws/credentials` via `aws configure`, never in the repo or `.env`.