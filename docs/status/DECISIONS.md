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
