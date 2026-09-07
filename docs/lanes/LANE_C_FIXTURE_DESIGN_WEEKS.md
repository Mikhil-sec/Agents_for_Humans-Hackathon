# Fixture design — the four weeks

Lane C, `c/fixtures-full`. Drafted 2026-09-05 with Claude (web).
Companion to `docs/lanes/LANE_C_FIXTURE_DESIGN.md`, which settles the time axis and
`merchant_history.json`. This one covers `inbox/`, `transactions.json`,
`calendar.json`, the nine scenarios, signal ids, and the scenario manifest Mikhil
asked for in `FOR_YORVAN.md` §4.

---

## 1. Two corrections to the earlier design

### 1a. Dates are offsets from `--as-of`, not absolute

The earlier doc fixed the calendar to absolute dates (week 1 = 27 Jul, as-of =
26 Aug). That breaks the moment anyone bumps `DEFAULT_AS_OF` — which the same doc
recommends doing before submission so the demo doesn't look stale. Bump the
constant and the deliberate three-day gap becomes a three-week one.

**The seeder computes every timestamp as `as_of - <fixed offset>`.** Bumping the
constant then shifts the whole world coherently and every relationship inside it —
the gap, the four-week span, the merchant-history window — is preserved.

```
week_1_monday = as_of - 34 days      week_3_monday = as_of - 20 days
week_2_monday = as_of - 27 days      week_4_monday = as_of - 13 days
week_4_sunday = as_of -  3 days      household created = as_of - 41 days
```

`household.json`'s `created_at` is currently the hardcoded `2026-07-20T09:00:00Z`.
It becomes `as_of - 41 days`, which reproduces that exact value at the current
default.

**Consequence: signal ids must not contain dates.** `sig_fitlife_renewal`, never
`sig_fitlife_renewal_20260821` — otherwise a bump to `--as-of` renumbers every id
and silently breaks Mikhil's A8 re-keying, which is the failure he explicitly
warned about.

### 1b. Merchant-scoped policies cannot move the curve

This is the structural one, and the earlier design got it wrong.

Household bills are **monthly**. The window is **four weeks**. So a given merchant
appears roughly once. "Week 1 asks about British Gas, weeks 2–4 stay silent" cannot
happen — British Gas doesn't recur inside the window at all. A merchant-scoped
policy learned in week 1 has nothing left to apply to.

`PolicyScope` has four members and only one of them is `MERCHANT`. The lever is
**`CATEGORY` and `ACTION_KIND`**:

| Week 1 ask | Policy the user grants | What it covers later |
|---|---|---|
| British Gas gas bill, £84.20 | `CATEGORY` utilities under £150 | Octopus, Thames Water, Hyperoptic in weeks 2–4 |
| Sainsbury's receipt filed | `ACTION_KIND` `file_record` | Every receipt thereafter |
| Shell transaction tagged | `ACTION_KIND` `tag_merchant` | Every uncategorised merchant thereafter |

This is a better product story than the one in the brief, not just a workaround. The
agent learning *classes* of decision — "utilities under £150 are fine" — is a
stronger claim than learning one merchant at a time, and it is what makes the
interrupt rate fall at a rate a viewer can see inside four weeks.

Keep one merchant-scoped policy anyway: the README's own example is
"always auto-approve British Gas under £150", and it should appear somewhere. Grant
it in week 1 alongside the category policy, and let the category one do the work.

---

## 2. The household

Two working adults and a toddler in nursery — the README's stated audience, and the
reason nobody noticed a gym charge for seventeen months.

`household.json` stays as it is: `hh_demo`, The Okonkwo-Bennett household,
Europe/London, GBP, digest at 08:00, quiet hours 22–07.

**Two suppliers, deliberately.** The test fixtures already have British Gas as gas
(£84.20) and Octopus Energy as electricity (£94.00). Keep both — splitting suppliers
is ordinary in the UK, and it gives the category policy something to generalise
*across* rather than a single merchant to memorise.

Keep **Streamly** as the invented streaming service, already used in
`conftest.py`. It is the one scenario that attributes shabby behaviour to a named
company, so it should not be a real one.

## 3. The recurring spine

Roughly four bills a week, which is what an ordinary UK household actually looks
like once you count everything.

| Merchant | Amount | Category | Week |
|---|---|---|---|
| Camden Council (council tax) | £168.00 | council_tax | 1 |
| British Gas (gas) | £84.20 | utilities | 1 |
| Little Acorns Nursery | £680.00 | childcare | 1 |
| Vodafone (line 1) | £18.00 | telecoms | 1 |
| Hyperoptic (broadband) | £32.00 | utilities | 2 |
| Vodafone (line 2) | £18.00 | telecoms | 2 |
| Dropbox | £9.99 | software | 2 |
| Streamly | £12.99 → £15.49 | entertainment | 2 |
| Thames Water | £34.10 | utilities | 3 |
| Google One | £7.99 | software | 3 |
| TV Licence | £13.75 | entertainment | 3 |
| Octopus Energy (electricity) | £94.00 | utilities | 4 |
| Aviva (contents) | £214.00 annual | insurance | 4 |
| FitLife | £38.00 | fitness | 4 |

Plus daily noise throughout: Sainsbury's, Shell, TfL, Boots, Pret. These are the
`file_record` / `tag_merchant` / `update_budget_ledger` volume, and they are what
grows the silent count once the two `ACTION_KIND` policies exist.

**Nursery and council tax stay above every threshold the user sets**, so they keep
asking in weeks 1 and 4. That is the point: a household that has granted three
policies still gets asked about the £680 one. It proves the engine is deterministic
rather than agreeable.

## 4. The nine scenarios

| Week | Scenario | Finding → Action | Tier | Outcome |
|---|---|---|---|---|
| 1 | Dentist confirmation clashes with the weekly sync | `appointment_needs_reply` → `reschedule_appointment` | CONFIRM | approve |
| 1 | Dropbox + Google One both at 2TB | `duplicate_service` → `cancel_subscription` | CONFIRM | **snooze** |
| 2 | Streamly £12.99 → £15.49 | `price_increase` → `downgrade_plan` | CONFIRM | **deny** — they keep it |
| 2 | Duplicate resurfaces after the snooze | `duplicate_service` → `cancel_subscription` | CONFIRM | approve |
| 3 | Same merchant, same amount, same day, twice | `unexpected_charge` → `dispute_charge` | **NEVER_AUTO** | approve |
| 3 | Thames Water triples, £34 → £102 | `usage_anomaly` → `set_reminder` | SILENT/NOTIFY | no money moves |
| 3 | Aviva renewal quote 22% above last year | `renewal_upcoming` → `draft_email` | NOTIFY | — |
| 4 | Free trial converting in 48h | `trial_converting` → `cancel_subscription` | CONFIRM | approve |
| 4 | **FitLife annual renewal, £456** | `unused_subscription` → `cancel_subscription` | CONFIRM | **left pending** |

Two of these carry most of the demo's weight.

**The double charge is the safety proof.** `dispute_charge` is `NEVER_AUTO`, so it
interrupts in week 3 *after* the user has granted three policies. No policy can
reach it. That is a ten-second argument on video that the tiers are real.

**FitLife is the live card**, left pending at the as-of date. The annual renewal
notice arriving in week 4 is the trigger — the agent has been filing those £38
charges silently for three weeks because there was no reason to raise them, and now
there is:

> **FitLife renews in 6 days — £456 for the year.**
> Last visit: 14 March 2025. You've paid £456 over the last twelve months.

## 5. The arc

Design targets, not authored outputs. The actual figures are whatever the policy
engine returns; the data is built so these are what it returns.

| Week | Interrupts | Silent | Autonomy |
|---|---|---|---|
| 1 | 9 | 5 | ~36% |
| 2 | 6 | 12 | ~67% |
| 3 | 3 | 19 | ~86% |
| 4 | 2 | 25 | ~93% |

Total action volume roughly doubles, and it needs a cause in the data: early on,
thin merchant history means many transactions resolve to `nothing_to_do`; as priors
accumulate, more become taggable and ledgerable. That is why the daily-noise
merchants matter.

**The README currently claims 43% → 86%.** These targets do not reproduce that, and
they should not be bent to. The number is measured, so whatever falls out is the
number — and the README needs updating once it does. Mikhil owns that file.

## 6. Signal ids

`sig_<merchant>_<what>`, lowercase, underscore-separated, no dates, no counters that
shift when the data does. The existing test fixtures already follow this —
`sig_gas_bill`, `sig_streamly_trial`, `sig_fitlife_charge`.

Threaded emails share a `thread_id`: `thread_streamly` already demonstrates the
pattern, and the snooze-then-resurface scenario needs one.

History records use `hist_<merchant>_<n>`, which is a different namespace and does
not need to be stable — nothing re-keys against them.

## 7. The scenario manifest

New artifact, requested in `FOR_YORVAN.md` §4, so Mikhil can re-key `scenarios.py`
against something explicit rather than reading the inbox and guessing.

`fixtures/scenarios.json`:

```json
{
  "fitlife_unused": {
    "week": 4,
    "finding_kind": "unused_subscription",
    "action_kind": "cancel_subscription",
    "risk_tier": "confirm",
    "expected_outcome": "pending",
    "signal_ids": ["sig_fitlife_renewal", "sig_fitlife_charge"],
    "note": "The live card. Renewal notice is the trigger; the charge is the evidence."
  }
}
```

One entry per scenario, nine total. It is a *derived* description of raw data rather
than raw data itself — but the seeder writes it, because the seeder is what knows
which ids carry which scenario. Worth flagging to Mikhil as a tenth file that
doesn't fit the five/four split cleanly.

## 8. Tests

1. Every distinct merchant in `transactions.json` has a key in `merchant_history.json`.
2. Every `signal_id` in `scenarios.json` exists in the raw files.
3. Signal ids contain no digits that encode a date — re-seeding at a different
   `--as-of` produces an identical id set.
4. Re-seeding twice at the same `--as-of` produces byte-identical files.
5. Every raw record round-trips through the `Signal` contract.
6. The full set passes `require_fixture_set`, and `get_providers(MOCK)` returns a
   bundle with `as_of` set.
