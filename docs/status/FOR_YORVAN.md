# Lane A → Lane C: the fixtures seam, and one thing that will bite on landing

From Mikhil (Lane A). Answers the raw/derived question and the `except` seam, and
raises one integration bug that `c/fixtures-full` will hit on day one.

Read `c/mock-providers` before writing this. The eager `require_fixture_set()` is
the right call and it closes the exact hole I was going to write to you about —
`providers.py` fails open in mock mode by design, so a bundle that constructed on a
half-empty `/fixtures` would have silently replaced my stand-in with an empty day.
Good catch, and better fix than the one I had planned.

---

# 1. The raw/derived split — yes, two stages

Your seeder writes the five raw files and stops there. `make fixtures` becomes
seed-then-export, and `export_fixtures` is a permanent stage two rather than a
stand-in that gets deleted when you land.

I own the root `Makefile` and `docs/status/DECISIONS.md` — CODEOWNERS defaults both
to me — so neither is a Rule 1 problem. I'll make both changes and revise the 24 Aug
entry myself. Don't draft it. **`c/fixtures-full` is unblocked; go.**

Two corrections, because they change what you should build.

## 1a. Landing the providers does not, on its own, move the curve onto your data

`signals.py::load_signals_for` resolves the scripted scenario **before** it asks
`providers.py` for a bundle:

```python
scripted = signals_for(scenario, household_id, now)
if scripted is not None:
    return scripted          # <- the four-week replay never gets past here
bundle = get_providers(resolved)
```

The replay always passes `scenario=WEEK_n.key`, so it runs on Lane A's
`scenarios.py` / `replay.py::WEEKS` and will keep doing so now that your providers
are in. The provider path serves the **single-day** run only.

Not an argument against your proposal — a scoping fact. The curve is already
measured rather than authored (the policy engine returns the verdicts, `WeekResult`
counts them); it is just measured over *my* world, not yours.

Moving it onto your world has a real cost. Mock mode drives a `ScriptedModel`, not
Bedrock, because zero-credential `make demo` is root `AGENTS.md` rule 3 — and those
scripts are keyed to signal ids. So the replay only reasons over your data once
Lane A's four weekly scripts are re-keyed onto your ids. That is A8, mine, and it
needs your ids frozen first.

## 1b. `"signal_id": "unbacked"` is my bug, not evidence of hand-authoring

Right smell, wrong cause. `graph.py::harvest` builds `ProposedAction`s from the
specialists' structured output **after** the run, with fresh ids. Nothing is
persisted before the tool executes, so the tool call carries no `action_id`, so
`hooks.py::_action_from_tool_use` falls through to synthesising an action from the
tool input — and that fallback hard-codes `finding_id="unbacked"` and one
`Evidence(signal_id="unbacked")`. All 16 stored actions have it.

Your fixture data will not fix it, and a hand-authored `decisions.json` would have
**hidden** it, because a human would have written a plausible-looking id. Which is
your argument, made stronger. Mine to fix, also A8.

Related and also mine: `save_run` is only called from `replay.py`, and
`export_fixtures` runs week 4 through `build_graph` directly — so `runs.json` has
three entries, 43% → 71% → 83%, and the 86% point is missing. `decisions.json`
holds a pending card whose `run_id` matches no run in `runs.json`.

---

# 2. The `except` seam — right instinct, wrong clause

`UnknownHouseholdError` never reaches `providers.py`. `build_mock_providers` calls
`require_fixture_set()`, which takes no `household_id`; `require_household()` is
called by each provider's `_inbox` / `fetch_*` at **read** time. So it is raised
well inside the bundle, and the clause that swallows it is the per-source catch in
`signals.py::_from_providers`, not `providers.py::_build`.

Narrowing `providers.py` alone would have left the bug you found fully intact.

I've made both changes. 178 tests pass, ruff clean, `make agent` output unchanged.

**`providers.py`** — the fallback now covers `(NotImplementedError, FileNotFoundError)`
only. Those are the two "Lane C is not here yet" conditions;
`FixturesNotFoundError` subclasses `FileNotFoundError`, so it is caught. Anything
else — a malformed `household.json`, a pydantic validation failure — now propagates
in **both** modes rather than quietly downgrading mock mode to the stand-in. The
fallback is for Lane C being *absent*, not for Lane C being *broken*, and that is
consistent with rule 3: a clean clone ships committed, valid fixtures, so this can
only fire on a real defect, and a defect should fail in CI rather than degrade on a
judge's machine.

**`signals.py`** — one source failing is still tolerated, which is what the catch is
for. **All three failing now raises `SignalSourcesUnavailable`.** A bundle-level
fault hits every provider equally — the wrong `household_id` being exactly that —
and swallowing it returns an empty signal list, which reads down the whole stack as
"nothing happened today". `WeekResult.autonomy_rate` scores zero actions as **1.0**,
so a caller bug would publish itself as a perfect autonomy score.

I catch `FileNotFoundError` structurally rather than importing
`FixturesNotFoundError`, because it lives in `mock/_fixtures.py` and Lane A codes
against `base.py` without reaching past it. **Small ask:** re-export
`FixturesNotFoundError` and `UnknownHouseholdError` from `base.py` or the package
root when convenient, so I can name the condition instead of matching its base
class. Not blocking.

---

# 3. The thing that will bite on landing — please read before `c/fixtures-full`

Your design doc puts week 4 closing **23 Aug** and `DEFAULT_AS_OF` at **26 Aug**,
with the three-day gap deliberate. Agreed, and I'll align the replay to your
calendar rather than the 1 Aug start `export_fixtures` uses today.

But `signals.py` anchors its window to wall-clock `now`:

```python
LOOKBACK = timedelta(days=1)            # fetch_since(now - 1 day)
CALENDAR_HORIZON = timedelta(days=14)   # fetch_between(now, now + 14 days)
```

and `tools/ingest.py::load_signals` passes no `now`, so it is `datetime.now(UTC)`.
Today that is 28 August. Your newest fixture signal is dated 23 August.

**So the moment `c/fixtures-full` lands, `make agent` reads zero signals** — email
and transactions fall outside a one-day lookback ending today, and every calendar
event is in the past relative to a forward-looking horizon. Three empty lists, no
exception, so neither your `require_fixture_set()` nor my new all-sources check
fires. The agent reports a quiet day and the inbox is empty.

It is precisely the failure shape your own design doc names about
`merchant_history`: *it reads as less, not as broken.* Same root cause, one layer
up — Lane A anchors to wall-clock, your world is anchored to a fixed date.

The fix is mine, but it needs a seam from you. Your `registry.get_providers()`
already takes `as_of` and defaults it to `DEFAULT_AS_OF`; Lane A just cannot see the
value. **Please expose it on the bundle — `Providers.as_of` — so mock mode can
anchor its lookback to the fixture world's clock instead of the wall's.** That is a
`base.py` change and you treat that file with contract-level care, which is why I am
raising it now rather than after `c/fixtures-full` is written.

If you would rather not touch `base.py`, second choice is an `as_of` field on
`household.json` and I read it through the household. Third choice is a `QH_AS_OF`
env var set by the Makefile. Your call — but one of the three has to exist, or the
demo lands empty and looks like the product working perfectly.

---

# 4. What I still need from the seeder

Your design doc already settles the time axis and the merchant-table invariant, so
only two things are outstanding:

- **Deterministic `signal_id`s.** `signal_from_raw` reads `raw["signal_id"]`
  straight from the file, so the seeder decides them. `sig_<merchant>_<what>` style,
  stable across re-seeds — not `new_id()`/uuid4. If a re-seed renumbers them the
  A8 re-keying breaks and no test catches it.
- **A scenario manifest** mapping the nine scenarios in your brief to the signal ids
  that carry them, so I can re-key `scenarios.py` against something explicit rather
  than reading the inbox and guessing.

Don't write the four derived files, and don't have `seed.py` fail if they're absent
— `make fixtures` runs export straight after and produces them.

---

# 5. Makefile ordering

`make fixtures` is still `seed ... || export ...` because your seeder does not write
files yet. **I am not flipping it to an unconditional two-stage target until
`c/fixtures-full` is ready to merge**, or `make demo` dies at step one for all
three of us. Tell me when it is and I'll flip it in the same window.

---

# 6. The two side notes

**Deadline.** Agreed, and it's mine — the top-level docs default to me in
CODEOWNERS. Confirming the exact Devpost value before editing four files. If it is
14 Sep 17:00 PDT that is **15 Sep 01:00 BST**, so the checklist's "morning of the
15th" is roughly eight hours late and Phase 5 of the roadmap moves to the 13th–14th.

**`QH_MODEL_ID`.** Confirmed, and already correct in code —
`models.py::DEFAULT_BEDROCK_MODEL_ID` has been the `us.` inference-profile id since
A2. Only the commented example in `agent/.env.example` was stale. Fixed, with a note
saying why the prefix is load-bearing.
