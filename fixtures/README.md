# Fixtures

The seeded four-week household history the whole demo runs on. Owned by Lane C.

**Entirely synthetic.** No real person's data appears here. Merchants are real
UK brands used descriptively; amounts, dates and behaviour are invented.

Regenerate with:

    python -m quiet_hours_integrations.mock.seed --out fixtures/

They are committed so `make demo` works on a clean clone with no generation step.

## Files

| File | Contents |
|---|---|
| `household.json` | The household profile |
| `inbox/*.json` | One file per email. ~60% should be noise the agent correctly ignores. |
| `transactions.json` | Card and bank activity across four weeks |
| `calendar.json` | Events, including one that clashes with a dentist appointment |
| `merchant_history.json` | Twelve months of priors so BillAnalyst can answer "is this normal?" |
| `decisions.json` | Decision cards, for the fixtures API backend |
| `activity.json` | The audit trail |
| `policies.json` | Policies granted during the four weeks |
| `runs.json` | Run history, which produces the autonomy chart |

## The narrative these must produce

| Week | Decisions raised | Handled silently |
|---|---|---|
| 1 | ~9 | ~4 |
| 2 | ~6 | ~11 |
| 3 | ~3 | ~19 |
| 4 | ~2 | ~26 |

Scenario list is in [../docs/lanes/LANE_C_INTEGRATIONS.md](../docs/lanes/LANE_C_INTEGRATIONS.md).
Build the data backwards from this curve — it is the demo's headline chart.

**Lanes A and B: do not edit these.** Ask Lane C for a new scenario.
