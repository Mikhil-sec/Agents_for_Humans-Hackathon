# Decision log

Cross-cutting decisions that affect more than one lane. **Append new sections at the bottom. Never edit an existing entry** — if a decision is reversed, write a new entry that supersedes it and link back.

Anything here is binding on all lanes. If you disagree with a decision, open a new entry proposing the change rather than quietly working around it.

Use this for: contract changes, dependency additions everyone will use, changes to the risk tiers, changes to the demo narrative, deployment target changes, scope cuts.

---

## 2026-08-21 — Project shape

**Decision:** Build "Quiet Hours", an autonomous household-admin agent for the *Everyday Agents* track. Three lanes: A (agent), B (API + web), C (integrations + infra), with a documented two-person fallback in `docs/lanes/TWO_PERSON_FALLBACK.md`.

**Why:** The track rewards agents that "run quietly in the background and only ping you when there's a real decision to make". Strands' `interrupt()` primitive plus durable session management maps onto that description almost exactly, which makes it both a natural fit and a non-obvious use of the SDK.

**Affects:** everyone.

---

## 2026-08-21 — The interrupt is the product

**Decision:** The differentiating mechanic is **earned autonomy**. Every approval can create a policy; the policy engine then handles that class of action silently; the interrupt rate falls measurably over four simulated weeks. The autonomy trend chart is the demo's headline visual.

**Why:** Most hackathon entries will be a chatbot with tools attached. A visible, quantified reduction in how often the agent bothers you is a direct, demonstrable answer to the brief's own thesis, and it is hard to build without exactly the Strands features we are using.

**Affects:** A owns the mechanic, B owns the chart, C owns the fixture data that produces the curve. All three are required for the demo to land.

---

## 2026-08-21 — The policy engine is deterministic code, not a model

**Decision:** `agent/quiet_hours_agent/policy.py` contains no LLM call. It is pure functions over an explicit policy table.

**Why:** Learned autonomy must be auditable, explainable and revocable. A model deciding whether it needs permission is precisely the thing a user would not trust with their bank account — and a prompt can be argued out of a safety rule, whereas an `if` statement cannot. This is also a point worth making explicitly to judges.

**Consequence:** No policy may auto-approve a `NEVER_AUTO` action. Enforced in code and covered by a named test.

**Affects:** A primarily; B renders the policies this produces.

---

## 2026-08-21 — Mock mode is the default and must never break

**Decision:** Every external dependency sits behind a provider interface with `mock` and `live` implementations. `git clone && make demo` must produce a fully working system with no AWS account and no credentials.

**Why:** The rules require the project to install and run consistently, and a judge with four minutes will not configure OAuth. Mock mode is our guarantee that they see the product working.

**Affects:** C builds it, A consumes it, B mirrors it with `fixtures_server.py`.

---

## 2026-08-21 — Safety posture: drafts and requests, never sends and transfers

**Decision:** Even in live mode the agent creates email *drafts* and *scheduled payment requests*. The live Gmail provider has no send path in the codebase at all.

**Why:** An agent with unattended access to someone's email and money is a liability we are not going to ship in a hackathon, and the absence of the code is a stronger guarantee than a config flag. Stating this plainly in the README reads as engineering judgement rather than as a limitation.

**Affects:** C implements it, A must not work around it, B should surface it in the UI copy.

---

## 2026-08-21 — Money is integer minor units

**Decision:** `Money(amount_minor: int, currency: str)`. Never floats, anywhere, in any lane.

**Why:** Float arithmetic on money produces off-by-a-penny bugs that are painful to track down, and we are demoing a financial product.

**Affects:** everyone. `formatMoney()` in the TypeScript contracts is the only place division by 100 should occur.

---

## 2026-08-24 — DynamoDB single-table layout

**Decision:** One table, name from `QH_TABLE_NAME` (default `quiet-hours`). A record's own
id is the partition key; a GSI named `gsi1` answers every household query. The contract
model is stored as **JSON text** in a `body` attribute.

| Attribute | Example | Purpose |
|---|---|---|
| `pk` / `sk` | `DECISION#dec_abc` | the record's own id; both the same |
| `gsi1pk` | `HH#hh_demo#DECISION` | one household's records of one type |
| `gsi1sk` | `2026-08-24T07:15:00Z` | the record's timestamp, so lists come back ordered |
| `type` | `DECISION` | one of `ACTION`, `DECISION`, `ACTIVITY`, `POLICY`, `RUN` |
| `body` | `{"decision_id": ...}` | the contract model, `model_dump_json()` |

**Why id-as-partition-key:** `get_decision(decision_id)` takes no `household_id` — Lane B's
`POST /api/decisions/{id}/respond` only has the id from the URL. Partitioning by household
would make every read a scan or a second lookup. The household query is the *secondary*
access pattern, so it lives on the secondary index.

**Why JSON text rather than typed attributes:** DynamoDB has no float type and
`Finding.confidence` is a float. Typed attributes would mean a `Decimal` conversion on every
write and every read, in both Lane A's code and Lane B's, forever. Storing
`model_dump_json()` output means the bytes in the table are exactly the frozen contract
shape, and both lanes parse them with the same pydantic models. It costs the ability to
query on an inner field, which nothing in the product does.

**Status filtering is client-side.** `list_pending_decisions` reads the household's
decisions and filters on `status`. Folding status into `gsi1pk` would make resolving a card
a delete-and-reinsert across two partitions, and a crash between the two would lose the card.

**Reference implementation:** `agent/quiet_hours_agent/store.py::DynamoStore`, with the
`Store` Protocol at the top of the same file. Tests in
`agent/tests/test_persistence_live.py`.

**Affects:** A writes it (done), B reads it, C provisions the table and the `gsi1` index in
CDK. **No pagination** — every list method takes the first page, which is right for a demo
household and would need revisiting for a year of activity.

---

## 2026-08-24 — main was force-pushed away, and how it was restored

**What happened:** `main` was force-pushed to an unrelated single commit containing 13
files — Lane B's `api/` and `web/` work plus a LICENSE and an architecture note. That
removed `/contracts`, `/agent`, `/integrations`, `/fixtures`, `/infra`, `/docs`, the
`Makefile` and every `AGENTS.md` from the default branch. The cause was pushing from a
directory that was never a clone of this repository.

**Decision:** the orphan commit was **merged** into the real history rather than reverted,
so Lane B's work and its authorship are both preserved. `main` now has two roots. No force
push was needed to restore it, because merging made the orphan an ancestor.

**Nothing was lost.** Three backup branches exist and should not be deleted until everyone
has confirmed their work is present:

| Branch | What it holds |
|---|---|
| `backup/main-before-force-push` | `main` exactly as it was before |
| `backup/diya-first-commit` | the force-pushed commit, standalone |
| `backup/miks-branch` | Lane A's branch at the time |

**Resolutions made during the merge:** the project's MIT `LICENSE` was kept over an
incoming truncated Apache 2.0 header (a fresh-repository default, not a relicensing
decision); `api/__pycache__/*.pyc` were dropped as build artifacts already in
`.gitignore`.

**How to avoid a repeat:** always `git clone` this repository rather than pushing a local
folder into it, work on a lane branch (`a/`, `b/`, `c/`), and open a PR. Branch protection
on `main` was removed on 22 Aug; **turning it back on would have prevented this entirely**
and is recommended.

**Affects:** everyone.

---

## 2026-08-24 — /fixtures is generated from a real agent run until Lane C's seeder lands

**Decision:** `make fixtures` tries `quiet_hours_integrations.mock.seed` first and falls
back to `python -m quiet_hours_agent.export_fixtures`, which runs the agent in mock mode
and writes what the run actually produced.

**Why:** Lane C's seeder is still a stub, so `make fixtures` failed, `/fixtures` held no
JSON, and every Lane B screen returned 404. `make demo` was dead at step one — the thing a
judge runs, and root `AGENTS.md` rule 3.

**Why generated rather than hand-written:** everything written comes out of `store.py`,
which only ever holds validated contract models, so the fixtures are contract-correct by
construction. Hand-written fixtures drift from `/contracts` silently.

**This is not a replacement for Lane C's seeder.** It reads nothing from `/fixtures` and
invents no inbox. When Yorvan's seeder lands it takes precedence again with no further
change.

**Affects:** A generates it, B reads it, C supersedes it.

