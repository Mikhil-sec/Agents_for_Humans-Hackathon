# Progress — Lane B

**Owner:** Diya
**Directories:** /api, /web
**Branch prefix:** `b/`

---

## How to use this file

**Append new entries at the bottom. Never edit, reorder, summarise or tidy earlier
entries.** Another session — possibly another person's AI assistant — may be reading
them, and rewrites are the number one cause of merge conflicts in a shared repo.

This file is the handover between sessions. Any AI coding assistant picking up work in
Lane B should read the last two entries before doing anything.

**Only Lane B writes to this file.** Other lanes: use your own.

Template:

```markdown
## YYYY-MM-DD — session with <tool name>

**Done**
- ...

**In progress**
- ... (branch: `b/...`)

**Blocked / needs a human**
- ...

**Notes for the next session**
- ...
```

---

## 2026-08-21 — repo scaffolded

**Done**
- Lane B directories created and documented
- Read your brief: `docs/lanes/LANE_B_*.md`

**Next**
- See "Build order" in your lane brief

**Notes for the next session**
- Contracts freeze on 2026-08-24. Raise any shape you need before then — after that
  it is a `contract:` PR with two approvals.

---

## 2026-09-04 — session with Claude Code

Picked up from the 2026-08-21 scaffold entry. Lane A's 2026-08-24 note listed what
was broken here; all of it is addressed below.

**Done — API (B1)**

- Rebuilt `/api` on a store seam. `app/backends/base.py` is a `Backend` Protocol
  returning **contract models**; `fixtures.py` and `dynamo.py` implement it, and
  `QH_BACKEND` picks one. Routers, paging and the digest are written once against
  the Protocol.
- Every frozen route is live: decisions (list / get / respond), runs (list / get /
  trigger / SSE stream), activity, policies (list / revoke), `brief/latest`,
  `health`. All wrapped in the contract `Page` envelope with cursor paging, and
  every response carries `contract_version` in the body **and** an
  `X-Contract-Version` header.
- Two additive routes, both serving existing contract models: `GET /api/household`
  (the web app needs `Household.timezone` to convert UTC at render time —
  hardcoding it in `/web` would have been a contract violation waiting to happen)
  and `GET /api/brief/latest/preview` (+ `.txt`) for the digest template.
- Stable `ApiError` codes with a real handler chain (`app/errors.py`); pydantic
  validation failures come back as `invalid_request`, not FastAPI's `{"detail": ...}`.
- The fixtures backend is a stub of the *store*, not of the product: answering a
  card resolves it, writes the activity row, and creates the policy the button
  previewed — held in memory, so a restart resets it. `/fixtures` is never written
  to. Everything loaded is parsed through the frozen models, so a drifted fixture
  fails at load with a field name rather than in front of a judge.
- `respond` rejects a choice the card never offered (it would strand the run at an
  interrupt with no matching branch) and a body `decision_id` that disagrees with
  the URL. `session_id` / `interrupt_id` / `interrupt_name` are echoed untouched —
  there is a test asserting exactly that.
- Daily digest email in `app/digest.py`: HTML (tables, inline styles) plus a text
  alternative. `send_digest()` is never called by a route and raises unless
  `QH_DIGEST_TO` and `QH_SES_SENDER` are both set.
- **43 pytest tests**, `ruff check api` clean.

**Done — web (B2 to B5)**

- `/web` had no `package.json`, no `tsconfig.json` and an empty `package-lock.json`
  — it could not install or run. Scaffolded properly: Next 15.5, React 19,
  TypeScript strict, Tailwind v4, ESLint flat config with `no-explicit-any` as an
  error.
- Types come from `contracts/typescript/index.ts` via the `@contracts` alias
  (`experimental.externalDir` is what lets Next compile a file above the project
  root). Nothing redeclares an API payload; there is no `any`.
- All four screens built: Today (cards plus the empty state), Activity (one trail,
  filterable, rows expanding to rationale, the permitting rule and the decision's
  evidence), Rules (plain-English policies, usage counts, one-click revoke,
  revoked rules kept), Insights (the autonomy chart, stat tiles, and the "why the
  line falls" note).
- States built explicitly: empty, loading (skeletons), error (per-code copy),
  contract-mismatch banner, decision-expired, offline banner. "Empty" and "broken"
  deliberately look nothing alike — in this product an empty screen is success.
- Light and dark, set before first paint, with a header toggle. One accent colour,
  used only for "this needs you".
- The chart is hand-rolled SVG (no chart library). One axis — money is a stat tile,
  never a second y-scale. The two-colour palette was **validated, not eyeballed**,
  against each mode's own surface: light `#eb6834` / `#15a06f`, dark `#d95926` /
  `#199e70`. Legend, direct labels and a "Show numbers" table mean identity is
  never colour-alone.
- SSE: "Check now" triggers a run and narrates the graph's stages live.

**Verified**

- `pytest -q` in `/api`: 43 passed. `ruff check api`: clean.
- `npm run build`, `npm run typecheck`, `npm run lint` in `/web`: all clean.
- **Driven in a real browser (headless Chrome over CDP), not just built.** With the
  API on `QH_BACKEND=fixtures`: the pending card renders with `why_asking` and the
  policy preview, "Show me why" expands the evidence, "Always do this" resolves it,
  Today falls back to *"Nothing needs you today."*, the exact previewed rule
  appears on `/policies`, Revoke moves it to Revoked, the answer shows in the trail
  as "Approved, and set a rule", and Insights updates. Dark mode repaints
  correctly. The digest preview renders.
- The Playwright MCP server would not connect this session (`CONNECT_TIMEOUT`), so
  the browser driving was done with Chrome DevTools Protocol directly. Same
  confidence, different tool.

**Not verified**

- **The `live` backend has never touched real AWS.** `app/backends/dynamo.py` is
  written against the single-table layout in `DECISIONS.md` (2026-08-24) and the
  resume payload in `PROGRESS_A.md`, but no AgentCore deploy exists yet and there
  is no DynamoDB table to point at. Treat it as unexercised code.
- `make demo` could not be run here — `make` is not installed on this machine. The
  equivalent commands were run directly and work.
- No component or end-to-end test suite in `/web`. `npm test` runs typecheck and
  lint, which is not the same thing.

**Blocked / needs a human**

- **`make demo` does not start anything.** The target runs `fixtures` and then
  prints "Starting Quiet Hours in mock mode..." without launching the API or the
  web app — but the README then says "open http://localhost:3000". A judge
  following the README gets a blank browser. The `Makefile` is at the repo root and
  is not Lane B's file: someone needs to make `demo` actually run `api` and `web`,
  or the README needs to say "run `make api` and `make web` in two terminals".
  Flagging rather than editing.
- **The live demo link is still a TODO in the README** and it is worth real points.
  Amplify hosting is `/infra` (Lane C). The app builds statically clean, so it is
  ready to deploy the moment there is somewhere to deploy it to.
- **A fixture inconsistency for Lane A/C:** `daily_brief.json` references
  `run_f7304a60f0534f5e85bd4834`, which is not in `runs.json`, and the one pending
  decision belongs to that same missing run. Nothing breaks (the API serves the
  brief as written and derives the counts), but the chart cannot plot the run the
  live card came from.
- **`DecisionCard` carries no action `params`**, so the `edit` choice cannot offer a
  real parameter editor — it currently sends the user's note instead. If `edit` is
  meant to be a first-class choice, the card needs the proposed action's params,
  and that is a `contract:` PR. Not urgent: no fixture card offers `edit`.

**Notes for the next session**

- The SSE progress frames are the one shape in the app not from `/contracts`, and
  that is deliberate — `/contracts` describes stored state, and nothing persists a
  progress frame. The types are mirrored in `api/app/routes/runs.py` and
  `web/lib/stream.ts`. If they ever need to carry stored state they should send the
  contract model whole, as `run.completed` already does.
- `web/lib/errors.ts` mirrors `api/app/errors.py`. Changing an error code means
  changing both in the same PR.
- Removed as superseded, all inside Lane B: `api/config.py`,
  `api/fixtures_server.py`, `api/requirements.py` (empty and misnamed),
  `api/app/fixtures_server.py` (the scaffold stub), and `web/lib/formatters.ts`
  (a local money formatter that divided by 100 — the lane rule says use the
  contracts' `formatMoney`). `api/main.py` is now a two-line re-export of
  `app.main:app` so both `uvicorn main:app` (the root `Makefile`) and
  `uvicorn app.main:app` (`api/AGENTS.md`) keep working without editing the
  Makefile.
- `docs/lanes/LANE_B_WEB.md` line 72 was updated to point at
  `api/app/backends/fixtures.py`.
- There is an untracked full duplicate clone of the repo at
  `Agents_for_Humans-Hackathon/` inside the working tree, sitting at the same
  commit. Nothing was written to it. Worth deleting before it gets committed by
  accident.
