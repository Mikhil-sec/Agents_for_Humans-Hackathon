# web — the decision inbox (Lane B)

Next.js 15 (App Router), TypeScript strict, Tailwind v4. No UI kit and no chart
library: the whole app is about 1,400 lines including the SVG chart.

```bash
cd web
npm install
npm run dev            # http://localhost:3000
```

It needs the API running with the fixtures backend:

```bash
cd api
QH_BACKEND=fixtures uvicorn app.main:app --reload --port 8000
```

Point `NEXT_PUBLIC_API_URL` at it (`.env.example` has the default). You never need
the agent running to work on any screen here.

## The one rule

**This is not a chat app.** It is a decision inbox that is usually empty. The best
screenshot of this product is the empty state: *"Nothing needs you today."* If a
composer ever appears on the main surface, the product thesis is dead.

## Screens

| Route | Purpose |
|---|---|
| `/` | Today — pending decision cards, or the empty state, with what was handled silently below |
| `/activity` | The audit trail — everything the agent did, filterable, each row expanding to its rationale and evidence |
| `/policies` | Rules you have granted, in plain English, with a one-click revoke |
| `/insights` | The autonomy chart — decisions raised falling, actions handled silently rising |

## Where things live

| Path | What it is |
|---|---|
| `lib/api.ts` | The typed client. Every payload type comes from `@contracts`. |
| `lib/errors.ts` | The API's stable error codes and the copy for each. Mirrors `api/app/errors.py`. |
| `lib/format.ts` | Money via the contracts' `formatMoney`, timestamps converted to the household timezone at render time. |
| `lib/useResource.ts` | Loading / error / offline / refresh, in one hook. |
| `lib/stream.ts` | The SSE run stream. The only shape here not from `/contracts`, and deliberately so — see the file. |
| `components/DecisionCard.tsx` | The core component. Read its header before changing it. |
| `components/AutonomyChart.tsx` | The headline visual. Palette is validated, not chosen by eye. |

## Rules that are not style preferences

1. **Types come from `contracts/typescript/index.ts`**, imported as `@contracts`.
   Never redeclare an API payload type locally. No `any` — the lint config makes
   it an error.
2. **Money goes through `formatMoney()`.** `amount_minor` is an integer count of
   minor units. Nothing here divides by 100.
3. **Timestamps are UTC on the wire**, converted to `Household.timezone` at render
   time only.
4. **`why_asking` is always visible.** Never behind a disclosure.
5. **`creates_policy_preview` is rendered** before any `*_always` button.
6. **Every `switch` on an enum has a default branch.** Lane A can add a
   `FindingKind` or a `DecisionChoice` mid-build; unknown values degrade, never
   throw.
7. **The contract-version banner stays.** A quiet screen is what success looks
   like in this product, so a stale deploy cannot be allowed to look the same.

## States

Built explicitly, because this is where a product feels finished: empty, loading,
error, contract-mismatch, decision-expired and offline. `lib/errors.ts` has copy
for each failure the API can report.

## Theme

Light and dark, set before first paint by a small script in `app/layout.tsx`, with
a toggle in the header. One accent colour, reserved exclusively for "this needs
you" — nothing else in the product may use it.

## Checks

```bash
npm run typecheck      # tsc --noEmit
npm run lint           # eslint
npm run build          # production build
npm test               # typecheck + lint (there are no unit tests yet)
```

## Not done yet

- No component or end-to-end test suite. The screens have been driven manually in
  a real browser; that is not a substitute.
- No deploy. Amplify hosting lives in `/infra`, which is Lane C's.
