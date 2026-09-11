# Fixture design — dates and merchant history

Lane C, `c/fixtures-full`. Drafted 2026-08-26 with Claude (web). Agreed with Yorvan.

This is the spec for the *raw input* half of the fixture set. It covers the time
axis and `merchant_history.json`. Week-by-week signal design (`inbox/`,
`transactions.json`, `calendar.json`) follows separately.

Nothing here depends on Mikhil's outstanding raw/derived decision — that governs
which component *emits* the derived files, not what the world contains.

---

## 1. Reference date

The seeder takes `--as-of`, defaulting to a **fixed constant**: `2026-08-26`.

Reproducible by default; refresh before submission by bumping the constant.

### Why this is not just a preference

`MockTransactionProvider.merchant_history` currently computes its cutoff as
`datetime.now(UTC) - timedelta(days=30 * months)` — anchored to wall-clock now,
not to the fixture world's reference date.

With fixed fixture dates and a `now()` anchor, the oldest priors silently age out
of the window as real time passes. Run the demo in November and FitLife's history
is materially thinner, with no error — the card just has less evidence behind it.
That is the same failure shape as the fallback regression fixed on 2026-08-26:
it reads as *less*, not as *broken*.

**Required change (Lane C, our own file):** anchor `merchant_history` to the
reference date rather than `now()`. Options: read the as-of from `household.json`,
or accept it as a provider constructor argument. Either is in-lane. Add a test that
pins the window against a fixed as-of so this cannot regress.

## 2. Calendar

```
Mon 20 Jul 2026   household created (already in household.json, keep it)
                  12 months of bank history imported on connection
Mon 27 Jul – Sun  2 Aug   Week 1
Mon  3 Aug – Sun  9 Aug   Week 2
Mon 10 Aug – Sun 16 Aug   Week 3
Mon 17 Aug – Sun 23 Aug   Week 4
Wed 26 Aug                as-of; week 4's decision card still pending
```

Notes:

- The week of 20 July is onboarding. Accounts connect, twelve months of history
  imports, no agent runs. This gives the priors a legitimate origin — twelve to
  twenty-four months on connection is how open banking actually behaves.
- The three-day gap between week 4 closing and the as-of date is deliberate. The
  pending card has been sitting in the inbox for a few days when a judge opens it,
  which is more realistic than one raised seconds ago.
- Weeks are Monday-start and exist only as aggregation buckets for the autonomy
  chart. The agent runs daily.

## 3. `merchant_history.json`

Shape (from `MockTransactionProvider.merchant_history`):

```json
{
  "<exact merchant string>": [ {charge record}, {charge record}, ... ]
}
```

### Hard invariant

Lookup is `history.get(merchant, [])` — a plain dict lookup on an exact string.
If `transactions.json` says `"British Gas"` and `merchant_history.json` says
`"British Gas Ltd"`, the lookup returns `[]`, BillAnalyst has nothing to compare
against, and **nothing errors**. The finding just quietly fails to fire.

**The seeder must derive both files from one merchant table.** Add a test
asserting every distinct merchant in `transactions.json` has a key in
`merchant_history.json`.

### Coverage

Twelve months ending at the as-of date, except FitLife (see below). Amounts in
GBP minor units per the `Money` contract.

| Merchant | Records | Amount | Day | Notes |
|---|---|---|---|---|
| British Gas | 12 | £92.60–£96.40 | 5th | **Near-flat, ±£2.** This is the routine bill the agent learns to auto-pay; seasonal swing would make it anomalous and defeat its purpose |
| Hyperoptic | 12 | £32.00 flat | 12th | Second policy |
| Vodafone (×2 lines) | 12 each | £18.00 flat | 18th | Third policy. Two distinct merchant strings, e.g. `Vodafone (A)` / `Vodafone (T)` — or one merchant with two records per month |
| Camden Council | **10** | £168.00 | 1st | **Ten instalments, April–January.** Nothing in Feb or Mar — how UK council tax actually works. Falls out to exactly 10 in the window |
| Little Acorns Nursery | 12 | £680.00 | 1st | Above the £150 policy ceiling, so it always asks |
| Thames Water | 12 | £33.40–£35.20 | 22nd | The flat baseline that week 3's spike breaks |
| *(streaming — invented name)* | 12 | £12.99 flat | 8th | Makes £15.49 provably a rise rather than an assertion |
| Dropbox | 12 | £9.99 flat | 14th | Duplicate pair |
| Google One | 12 | £7.99 flat | 26th | Duplicate pair |
| Aviva (contents) | 1 | £214.00 | annual | Prior year's premium, for renewal comparison |
| FitLife | **17** | £38.00 flat | 3rd | See below |
| Sainsbury's | ~26 | £18–£94 varied | — | Volume for file/tag/ledger |
| Shell | ~10 | £48–£72 varied | — | Volume |
| TfL | ~20 | £2.80–£16.40 varied | — | Volume |

The high-volume three exist to feed the silent-action count. The autonomy curve's
denominator grows as merchant priors accumulate: early on, thin history means many
transactions resolve to `NOTHING_TO_DO`; as priors build, more become
file/tag/ledger-able. That is what makes total action volume roughly double across
the four weeks without hand-waving.

### FitLife

- Membership £38.00/month, charged on the 3rd.
- **Last visit 14 March 2025.** No visits since.
- Charges from April 2025 through August 2026 inclusive: **17 records, £646 total.**
- Inside the provider's default 12-month window (cutoff 2025-08-31):
  **12 records, £456** — first 2025-09-03, last 2026-08-03.
- Annual renewal **1 September 2026 at £456.00**.

The £456 coincidence is load-bearing and should be preserved. The card can say:

> **FitLife renews 1 September — £456 for the year.**
> Last visit: 14 March 2025. You've paid £456 over the last twelve months and
> haven't been once.

Same figure twice, two meanings. No arithmetic asked of the viewer, and every
number is one the 12-month window can actually produce. The five older records
stay in the file — they are true, and they reward anyone who widens the window —
but nothing on the card depends on them.

**Note this supersedes the brief's "eleven charges since March".** Eleven and March
are mutually inconsistent (eleven monthly charges implies a September 2025 last
visit). Resolved in favour of March, which is the more memorable detail and gives
seventeen months of genuine forgetting rather than eleven months of lapsing.

## 4. Naming

Real names where the fact is neutral and verifiable: Dropbox and Google One both
genuinely sell 2TB tiers, and that is the whole point of the duplicate scenario.
British Gas, Thames Water, Vodafone, TfL, Sainsbury's, Shell, Aviva — all ordinary
UK merchants doing ordinary things.

**Invent a plausible name for the streaming service.** That scenario attributes
slightly shabby behaviour — a price rise with the number buried — to a named
company. Cheap to avoid, and it is the only scenario where the merchant is
characterised rather than just charged.

Camden Council and Little Acorns Nursery are chosen as specific-but-unremarkable.
Per the brief: no "Acme Corp".

## 5. Tests the seeder should carry

1. Every distinct merchant in `transactions.json` has a key in `merchant_history.json`.
2. With as-of `2026-08-26`, `merchant_history("FitLife")` returns exactly 12 records
   totalling £456.
3. Camden Council has exactly 10 records, none in February or March.
4. British Gas priors vary by no more than £4, so the routine bill stays routine.
5. The full raw set passes `require_fixture_set` and every record round-trips through
   the `Signal` contract.
