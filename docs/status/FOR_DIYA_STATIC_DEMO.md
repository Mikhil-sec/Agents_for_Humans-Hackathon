# Lane A → Lane B — 11 September

From Mikhil.

**I have edited `/web`, which is your lane, and I want you to hear it from me rather
than find it in a diff.** Your §5 was right that a live demo needs no Bedrock. It turns
out it needs no AWS either. The whole thing is on GitHub Pages now.

---

## 1. First: yes to your section 4

**Merging `miks-branch` onto `main` yourself was the right call and I would have made
the same one.** `origin/main` was the version that prints three lines and exits. A PR
sitting overnight while a judge or either of us cloned that is a worse outcome than a
process rule bent once, in the open, with the reason written down. You did all three of
those things. Nothing to answer for.

Your other four asks are done:

- **`QH_PROVIDER_MODE=mock` is out of the `api` target.** You were right that nothing in
  `/api` reads it and that `QH_BACKEND` already defaults to `fixtures`. One-word fix, and
  `make demo` now survives a native Windows shell.
- **The pitch numbers are corrected** in `README.md`, `SUBMISSION_CHECKLIST.md` and
  `DEMO_SCRIPT.md`. More on this in §4, because I changed my mind once on the way.
- **The architecture diagram is in** — Yorvan landed it, and both it and your `main` are
  merged into `miks-branch`.
- **`estimated_annual_savings`**: thank you for taking it, and for keeping the realised
  figure and the projection apart. That distinction is the right one.

## 2. What I did in your lane, and why it is smaller than it sounds

**The live demo is a static export of `/web` on GitHub Pages.** No API to host, no
`QH_CORS_ORIGINS` to forget, no Amplify connect, no credentials — the two things neither
of us could get past. It is a push and a repo setting.

The reason it is a small diff is **your architecture, not my restraint**. Every read and
write in `lib/api.ts` already funnels through one `request()` function, and every page is
already `'use client'`. So the whole interception is one branch in one function:

```ts
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (STATIC_MODE) {
    const { staticRequest } = await import('./staticBackend');
    return staticRequest<T>(path, init);
  }
  // ...unchanged
```

The files I touched:

| File | Change |
|---|---|
| `lib/staticBackend.ts` | **New.** A port of `api/app/backends/fixtures.py` plus the route layer. |
| `lib/api.ts` | The branch above, and a `STATIC_MODE` const. |
| `lib/stream.ts` | One branch in `followRun` to replay the SSE frames on a timer. |
| `components/AppShell.tsx` | A `DemoBanner`, following your `ContractBanner` pattern. |
| `next.config.ts` | `output: 'export'`, `basePath`, `trailingSlash` — all gated. |
| `eslint.config.mjs` | `out/**` ignored. It did not exist before this. |

**`NEXT_PUBLIC_STATIC_DEMO=1` gates all of it and the default build is byte-for-byte the
same shape as before.** I re-ran `make demo` afterwards and drove it in a browser,
including answering a card against the real API and checking the rule appeared — the
seam I touched is the one every call goes through, so I was not going to take that on
trust.

## 3. What works on the hosted page

Verified in a browser, against a file server mimicking Pages' path layout rather than
against `next dev`, because the basePath and trailing-slash behaviour are exactly what
would break and `next dev` would not show it.

- All four screens, identical to the API-backed build.
- **Answering a card works.** It leaves the inbox, creates the rule the button previewed
  *verbatim*, writes the activity row, and flips the headline to "Nothing needs you
  today" with your empty state under it. That is the best beat in the product and it
  works on a page with no server behind it.
- Revoking a rule works.
- **"Check now" replays the run narration** — the same five frames as
  `api/app/routes/runs.py`, same order, same 600ms cadence.
- Zero console errors. No horizontal overflow at 390px. Dark mode intact, banner included.

`sessionStorage`, not `localStorage`, deliberately: a reload keeps the visitor's answer,
but a *new tab* gets the seeded world back with its pending card — because that card is
the demo and the next judge should meet it. There is a "Start over" in the banner too.

## 4. Two things I got wrong, so you can check my work

**I first corrected the pitch numbers to "43% → 86%".** Then I opened Insights and found
those percentages appear nowhere in your UI — the screen shows `4 → 1`, `3 → 6` and a
cumulative 73%. Your whole point in §6 was that the description must match what a judge
sees, and I had just written copy that did not. All three files now say **4 → 1
decisions, 75% fewer interruptions, 3 → 6 handled silently**, which is the chart.

**I also briefly claimed "19 of 26 actions" and then took it out**, because I could not
stand behind it. Your Insights tile says *19 of 26*, but `runs.json` sums to **27**
proposed actions. Your denominator is activity entries; the runs' denominator is proposed
actions, and the pending PhotoCloud cancellation is in one and not the other. Both are
defensible and I am not asking you to change yours — I only want you to know the two
numbers disagree before a judge asks which is right. **It is your page and your call.**

## 5. What I need from you

1. **Review the `/web` diff.** It is your lane and I would rather you owned it than
   tolerated it. If you want any of it shaped differently, say so and I will change it —
   or change it yourself, it is yours.
2. **The 26-vs-27 in §4.** Your decision entirely.
3. Nothing else. The Pages deploy needs a repo setting and a push, and both are mine.

## 6. One thing you should know about AgentCore

I could not do it, and it is not an effort problem: there is no AWS CLI and no
credentials on my machine, `/infra` is Yorvan's, and Bedrock still returns
`ValidationException: Operation not allowed` for every model — so a deployed agent would
fail its first request. It stays a bonus item we do not have. The hosted demo above is
the honest version of the same points, and it needs nobody's account.

Your Amplify spec is still committed and still correct, and if Yorvan clears Bedrock
before the 15th it is the better deployment. This was the one that did not depend on that.
