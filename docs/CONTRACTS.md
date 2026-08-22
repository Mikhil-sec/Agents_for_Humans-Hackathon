# Contracts — the frozen shared surface

`/contracts` defines every data shape that crosses a lane boundary. It is the reason three people can build in parallel without waiting on each other, and the reason a change made carelessly can break all three lanes at once.

**Status: FROZEN from 24 August 2026.**

---

## Why this exists

Lane A writes the agent. Lane B writes the API and web app. Lane C writes the integrations and infrastructure. None of them can finish without the others' output — unless the *shape* of that output is agreed in advance.

Once the shape is fixed:

- **Lane B** builds the whole decision inbox against `api/app/fixtures_server.py`, which serves static contract-shaped JSON. B never waits for the agent to work.
- **Lane A** builds the whole agent against the mock providers in `/integrations`, which read `/fixtures`. A never waits for real Gmail credentials.
- **Lane C** builds providers and fixtures validated directly against the Pydantic models with `pytest`. C never waits for the API or the agent.

When the lanes meet, they fit — because they were all built against the same contract, not against each other.

## What is in here

| File | Purpose |
|---|---|
| `contracts/python/quiet_hours_contracts/enums.py` | Every enumeration on the wire |
| `contracts/python/quiet_hours_contracts/models.py` | Every Pydantic model on the wire |
| `contracts/python/quiet_hours_contracts/version.py` | `CONTRACT_VERSION` |
| `contracts/typescript/index.ts` | TypeScript mirror for the web app |
| `contracts/schemas/generate.py` | Emits JSON Schema for review and codegen |

**Python is the source of truth. TypeScript is a hand-maintained mirror.** If they disagree, Python is right and the TypeScript file has a bug.

## The four load-bearing design decisions

Please do not "improve" these — each one is deliberate:

**1. Money is an integer count of minor units.** `Money(amount_minor=1799, currency="GBP")` is £17.99. Never a float, never a decimal string. Financial software that uses floats produces off-by-a-penny bugs that are miserable to find, and we are demoing a money product to judges.

**2. Every timestamp is timezone-aware UTC.** The household's IANA timezone lives on `Household.timezone` and is applied only at render time. A demo that spans "four weeks" of simulated data will produce timezone bugs if this slips.

**3. Findings and actions always carry `evidence`.** It is a required field with `min_length=1`. The user must always be able to ask "why did you think that?" — that is a core product promise and it is enforced by the type system rather than by discipline.

**4. `DecisionCard.why_asking` is required.** Not optional, not nullable. An agent that interrupts you without explaining why it could not decide on its own feels arbitrary. Making the field mandatory means the agent cannot forget.

## How to change a contract

Contract changes are expected — `FindingKind` in particular will probably grow during the build. They are not forbidden, just **loud**.

1. **Raise it first.** Post in the team chat and add a dated entry to `docs/status/DECISIONS.md` describing what needs to change and why.
2. **Open a dedicated PR** titled `contract: <what changed>`. It must touch **only** `/contracts` and this file. No feature code.
3. **Bump `CONTRACT_VERSION`** in `version.py`:
   - **MAJOR** — a field is removed, renamed, or its type narrowed. Breaking.
   - **MINOR** — a new optional field, or a new enum member. Additive and safe.
   - **PATCH** — docs or validation only.
4. **Update both sides.** Python *and* the TypeScript mirror, in the same PR.
5. **Get two approvals** from different lane owners. CODEOWNERS enforces this.
6. **Regenerate schemas**: `python contracts/schemas/generate.py`, commit the diff.
7. **Announce the merge.** Everyone rebases before continuing.

### What counts as breaking

| Change | Breaking? | Version bump |
|---|---|---|
| Add an optional field with a default | No | MINOR |
| Add a new enum member | No* | MINOR |
| Add a required field | **Yes** | MAJOR |
| Remove or rename any field | **Yes** | MAJOR |
| Narrow a type (`str \| None` → `str`) | **Yes** | MAJOR |
| Widen a type (`str` → `str \| None`) | No | MINOR |
| Change a field's meaning without changing its type | **Yes, silently** | MAJOR |

\* Adding an enum member is safe for producers but consumers must handle unknown values gracefully. Lane B: always give `switch` statements a default branch.

The last row is the dangerous one. A field whose *meaning* changes while its *type* stays the same will pass every test and produce wrong behaviour. If you are tempted, add a new field instead.

## Contract version checking

Every API response carries `contract_version`. The web app compares it against its compiled-in `CONTRACT_VERSION` and shows a loud banner on a major mismatch. Do not remove this check — during a three-week sprint with three people, a stale deploy rendering wrong data silently is a real risk.

## Freeze exceptions

Two changes may be made without the full ceremony, because they cannot break a consumer:

1. Adding or improving a **docstring or comment**.
2. Adding a member to **`FindingKind`** (purely additive, and Lane A will need this as triage gets smarter) — still requires a `contract:` PR, but one approval is enough.

Everything else needs the full process. When in doubt, use the full process; it costs twenty minutes and saves a day.
