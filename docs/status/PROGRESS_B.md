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

---

## 2026-09-11 — session with Claude Code

Working through Mikhil's `FOR_DIYA.md` (10 September) list.

**1. `make demo` from a clean clone — tested, and it works**

`make` was not installed here either, so I installed GNU Make 4.4.1
(`winget install ezwinports.make`) rather than approximating the recipes by hand.
Fresh `git clone` into an empty directory, into a throwaway venv so the editable
installs in my working tree were not repointed at a temp path.

| Step | Result |
|---|---|
| `make install` | works — 4m21s (pip x4 + `npm install`, 323 packages) |
| `make demo` | works — one command starts both, API on :8000 and web on :3000 |
| Data behind it | 4 runs (1/8/15/22 Aug), savings populated, brief headline correct |
| Insights chart | four evenly spaced weekly points, the 7 Sept gap is gone |
| **One Ctrl+C stops both** | **PASS** |

The Ctrl+C result is worth a word on method, because killing the parent process is
*not* the same test and gives a false failure: on Windows it orphans the Next dev
server holding :3000. I raised a real `CTRL_C_EVENT` with
`GenerateConsoleCtrlEvent` against the demo's console instead, which is what the
key actually does. Both processes exited and both ports released. Mikhil's
`$(MAKE) -j2 api web` is correctly wired.

**The one thing that is not fine: none of this is on `main`.** The fixes are on
`origin/miks-branch` (`73020c6`). `origin/main` is still `14a7c52`, where the
`demo` target prints four lines and exits, `runs.json` has three runs with null
savings, and the brief says "Nothing needs you today" over a pending card. **A
judge cloning `main` today gets the broken version.** `miks-branch` has to land on
`main` before the 15th; that is the single highest-value thing left.

**A Windows-only bug in the `api` target, found while testing**

`make demo` fails from `cmd.exe` or PowerShell — the web app starts, the API dies
immediately, and every screen renders its error state:

```
cd api && QH_PROVIDER_MODE=mock uvicorn main:app --reload --port 8000
'QH_PROVIDER_MODE' is not recognized as an internal or external command
```

`VAR=value command` is POSIX syntax. GNU Make on Windows uses `cmd.exe` as its
shell unless `sh.exe` is on PATH, so it works from Git Bash (how I tested it, and
how it behaves on macOS and Linux) and fails from a native Windows shell.

The fix is a deletion, not a rewrite: **`QH_PROVIDER_MODE` is not read anywhere in
`/api`** — I grepped. The API reads `QH_BACKEND`, which already defaults to
`fixtures`. Dropping the prefix from the `api` target makes it portable and
changes nothing functionally. The `Makefile` is Lane A's, so this is a request,
not a change I have made.

**2. The gitlink — done**

`git rm --cached Agents_for_Humans-Hackathon` (staged, not committed — the humans
do the git here). I also deleted the physical duplicate clone after checking it
was safe: clean status, no stash, no unpushed commits, sitting on `1f8acff`, which
is an ancestor of `main`. Nothing unique was in it.

**3. The favicon — done**

`web/app/favicon.ico` and `web/app/apple-icon.png`, generated from the clock mark
in the header so the tab matches the product. Multi-resolution ICO (16 through
256); the 16px frame is drawn with a heavier ring and a larger face, because the
hairline version turns to grey mush at that size.

A dark tile with a white glyph rather than a transparent dark stroke — a favicon
sits on whatever chrome the browser gives it, and dark-on-transparent vanishes
against a dark tab strip. The accent colour is deliberately **not** used: it stays
reserved for "this needs you" inside the product.

Verified with the Playwright MCP server (it connects again this session):
`/favicon.ico` returns 200 `image/x-icon`, Next injects the `<link rel="icon">`,
and `/` and `/insights` now report **zero console errors**.

**4. Amplify — prepared, not deployed, and I did not sink a day in it**

I cannot deploy: there is no AWS CLI on this machine, no `~/.aws`, and no `AWS_*`
in the environment. So the deploy itself is blocked on whoever holds credentials.

What I did instead, in-lane and small: `web/amplify.yml`, the build spec for step 7
of `infra/DEPLOY.md`, plus a "Deploying" section in `web/README.md` with the exact
console settings. It encodes the two things Amplify's auto-detection gets wrong
here — the app is not at the repo root (`appRoot: web`), and the build reads
`contracts/typescript/index.ts` from *above* `appRoot` via
`experimental.externalDir`, so the checkout must not be narrowed to `web/`.

**One correction to the assumption in `FOR_DIYA.md`, and it is good news.** The
note says a deployed app would have no working agent behind it, so it is not worth
much. That is true of the *live* path, but the judged path is mock mode, and mock
mode needs no Bedrock at all: `QH_BACKEND=fixtures` needs zero credentials, and the
web build never contacts the API — I verified this by stopping the API and running
`npm run build`, which succeeded. So a live demo link showing exactly what
`make demo` shows is achievable **while Bedrock is still broken**. It needs the API
hosted somewhere (step 4, `/infra`, Lane C) and `QH_CORS_ORIGINS` widened to the
Amplify origin. Worth ten minutes of Yorvan's time, not a day of anyone's.

**Also cleaned up**

`web/app/layout.js` — an untracked `create-next-app` default root layout
(`title: 'Next.js'`) sitting next to our real `layout.tsx`. Deleted. Two root
layouts in one App Router segment is at best ambiguous and at worst a build error;
it was never committed.

**Verified this session**

- `pytest -q` in `/api`: 43 passed. `ruff check api`: clean.
- `npm run typecheck`, `npm run lint`: clean. `npm run build`: clean, and clean
  again with the API stopped.
- Playwright MCP: `/` and `/insights` render with zero console errors.
- `make install` and `make demo` from a genuine clean clone of `miks-branch`.

**Not verified**

- The Amplify build spec has never been run by Amplify. It is a careful reading of
  the monorepo docs plus the constraints of this repo, not a tested deploy.
- The `live` DynamoDB backend still has never touched real AWS.

**Blocked / needs a human**

- **Merge `miks-branch` into `main`.** Everything above that makes `make demo`
  work lives only on that branch. This is the one that would actually cost us.
- **The `api` target's `QH_PROVIDER_MODE=mock` prefix** breaks `make demo` on
  native Windows shells. One-word deletion, Lane A's file.
- **AWS credentials** for the Amplify deploy, and Lane C's step 4 to host the API.
- Process: `14a7c52` went straight to `main` and this session's changes are sitting
  unstaged on `main` too. Mikhil has asked for `b/` branches and PRs from here —
  worth doing before the next push.
