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

---

# Lane A → Lane C — 10 September

From Mikhil. This replaces anything you may have had from me on the 7th; if you never
got that, nothing is missing — it is all folded in below.

**Read §1 and §5 first.** §1 is the one thing I need a decision from you on, and it is
the only thing blocking the last piece of Lane A. §5 is a possible way out of the
Bedrock wall that I do not think has been tried.

---

# 0. Where the project actually is

All three lanes are now merged together on my branch for the first time.
**206 agent + 50 integrations + 43 api = 299 tests, all passing.** Your
`c/mock-providers` and Diya's `main` both merged clean into `miks-branch`, with zero
file overlap in either direction.

I ran the whole thing end to end in a browser: your seeded fixtures → Lane A's agent →
the derived fixtures → Diya's API → the decision inbox. It works. Screenshots exist.

Everything in your `FOR_MIKHIL.md` §1, §3, §4 and §5 checked out against the repo.
Three corrections to the framing, then the real business.

**There is no `c/fixtures-full` branch.** Both your commits are on `c/mock-providers`
(`f80c51a` then `cd1d985`). Took me a minute to find them.

**Your 174 → 171 was measured against a Lane A one commit behind.** We had been at 178
since `9719f09`. Same three tests, so it was really 178 → 175. Not a disagreement —
just so the numbers reconcile when you next look.

**Nothing was red until I merged.** My tree had neither your providers nor a seeded
`/fixtures`, so my suite was green the entire time you were looking at a red one.

---

# 1. The one thing I need from you: `fetch_since` has no far edge

**This is the only thing blocking the replay re-key, and I do not want to decide it on
your behalf because of something you did deliberately.**

Your world reads beautifully per-week. I checked all four windows against
`scenarios.json` and the right signals land in the right weeks. But both read methods
are open-ended:

```python
def fetch_since(self, household_id: str, since: datetime, limit: int = 200) -> list[Signal]:
    """Return email signals newer than `since`, oldest first."""
```

There is no `until`. So asking for week 1 returns week 1 **and every week after it** —
61 of your 63 signals. The replay cannot isolate a past week.

Two ways to close it:

**(a) Add `until: datetime | None = None` to both `fetch_since` methods.** Keyword with
a `None` default, so nothing existing changes. It also makes the Protocol honest: a
read window has two edges.

**(b) I filter `occurred_at <= now` in Lane A** after reading. One line, no Protocol
change, I can do it today.

**Here is why I am not just doing (b).** `sig_thetimes_reminder` is dated
`2026-08-26T08:00`, eight hours *after* `DEFAULT_AS_OF` at midnight. A strict `<= now`
filter drops it, and the demo day goes from two live signals to one — quietly undoing
your "a judge opening the demo finds something waiting" design.

So there is a semantic question underneath, and it is yours:

> **Is `as_of` an instant, or a day?**

If it is a **day**, (b) is right and I filter to end-of-day; the daily run is
unaffected and I need nothing from you. If it is an **instant**, the two post-as_of
signals want moving a few hours earlier, and (a) is the cleaner fix.

Either works for me. I just need the answer. **One line back and I can finish this.**

---

# 2. Your §3 was right, and the bug is dead

`signals.resolve_now(explicit, bundle)` now resolves the run's clock in priority order:
explicit argument → `bundle.as_of` → `QH_AS_OF` env override → wall clock. Exactly the
pattern you documented on the attribute. Thank you for making it keyword-only with a
default; not one call site in Lane A had to change.

I reproduced it before fixing it, so the number is measured rather than assumed:
**wall clock returned 0 signals from your seeded fixtures; the anchored clock returns
2** — `sig_fitlife_renewal` and `sig_thetimes_reminder`, the two you designed to be
live at as-of. Your verification and mine agree exactly.

`export_fixtures` now raises `EmptyRunError` rather than writing a fixture set from a
run that ingested nothing, so this class of failure cannot come back silently. Your
point that an empty day is invisible was the right one to press.

Your two obsolete tests are rewritten rather than deleted. The absence warning is still
pinned — the absence is simulated now, since there is nothing left to fall back from.

---

# 3. Your §5 correction, and the on-screen proof of it

You said merchant-scoped policies cannot carry the autonomy curve, because household
bills are monthly and a merchant appears roughly once in four weeks.

**You were right, and it is now visible in the product rather than just in your
reasoning.** I found that `Policy.times_applied` had been declared in `/contracts`
since the freeze and incremented *nowhere* in the codebase — so the Rules page said
"not used yet" against every rule the household had ever granted. I fixed the counting.
Here is what it now reports for Lane A's own hand-written four weeks:

| Rule | Times applied |
|---|---|
| Always pay bill for British Gas up to £84.20 | **3** |
| Always pay bill for Thames Water up to £42.00 | **2** |
| Always reschedule appointment for Bridge Street Dental | **1** |
| Always cancel subscription for FitLife up to £38.00 | 0 |
| Always cancel subscription for Streamly up to £12.99 | 0 |
| Always cancel subscription for CloudBox up to £8.99 | 0 |
| Always downgrade plan for BroadbandCo up to £28.00 | 0 |

**Four of seven rules never fire again.** That is your argument, measured. The recurring
bills earn their keep; the one-off cancellations are dead weight the moment they are
granted. Your `CATEGORY` and `ACTION_KIND` scoping is the fix and I am not going to
argue with it.

Related, and useful to you: the policy gate now copies a finding's `category` onto the
action it produced. Before this week only `tag_merchant` ever supplied one, so
`CATEGORY` scope was nearly unreachable in practice. Your data will exercise it
properly now.

`fixtures/scenarios.json` is exactly the right shape and I would leave it where it is —
the seeder is what knows which ids carry what, so it belongs to the seeder.

---

# 4. Your §6, both done

**The Makefile is flipped.** `make fixtures` is now the unconditional two-stage target
— your seeder, then my exporter, in that order, no `||`. I ran both stages in sequence
against the merged tree: your seeder writes the raw world, my exporter writes the five
derived files, neither clobbers the other, ten files in `/fixtures`. The fallback was
dead code hiding a real ordering.

**The README's figures stay at 43% → 86% for now**, and I want to be explicit about why
rather than leaving you to wonder whether I ignored you. That is what the replay
*actually measures today* — so the README is currently correct, it is just measuring
Lane A's hand-written four weeks rather than your world. Your 36% → 93% becomes the
right pair the moment the re-key lands, which is blocked on §1. I have not bent
anything to hit either number and I am not going to.

---

# 5. Bedrock — one thing I think is worth trying before we write it off

Your read that it is account-level rather than model-specific is right: Nova failing
alongside both Claudes rules out the Anthropic use-case form and rules out model
access. But I went through the current AWS docs and I think there is a more specific
cause than "the account is broken", and it is one we can fix ourselves rather than wait
on case 178815493800207.

Model access is **enabled by default** now, *given* three account-level prerequisites.
A blanket failure across first- and third-party models points at one of these rather
than at Bedrock itself:

1. **AWS Marketplace IAM permissions.** The calling role needs
   `aws-marketplace:Subscribe`, `aws-marketplace:Unsubscribe` and
   `aws-marketplace:ViewSubscriptions`. Bedrock subscribes to a model through
   Marketplace on first invoke — so if these are missing, **every** model fails,
   including Nova. This is my main suspect and it fits the evidence better than
   anything else.
2. **A valid payment method** on the account for Marketplace purchases. A card-less
   account fails identically.
3. **Account tax/billing address in a supported country.** This one would not explain
   Nova, but it is thirty seconds to rule out.

Also worth a look: if the account sits inside an AWS Organization, a Service Control
Policy denying `bedrock:InvokeModel` produces exactly this wording.

Source: `docs.aws.amazon.com/bedrock/latest/userguide/model-access.html`, "Prerequisites
for successful model access".

**Please do not spend more than an hour on this.** The demo does not need Bedrock —
mock mode is the judged path and it works with zero credentials, which is a root
`AGENTS.md` rule. What Bedrock unlocks is only the two *bonus* items, the live demo
link and the AgentCore deployment. Both are "strongly recommended", neither is a hard
requirement. If those three checks do not clear it, we ship without it and say so
plainly in the README. That is a fine outcome.

---

# 6. What I need from you between now and the 15th

In priority order.

**1. The `as_of` answer in §1.** One line. It unblocks the last Lane A task.

**2. The architecture diagram → `docs/assets/architecture.png`.** This is a **hard
submission requirement**, not a nice-to-have — a submission can be rejected for missing
it, regardless of how good the project is. `docs/assets/` currently contains only a
README. It needs to be labelled with: user interface, Strands agent + agentic loop,
tools & integrations, AWS services, output. The material is all in
`docs/ARCHITECTURE.md` and the 30-second diagram in the root `AGENTS.md`.

**This is the single largest uncovered risk on the project right now.** Mikhil is
allocating the 13th to the diagram and the video, so the 13th is the deadline, but
earlier is better — it is the one item with nobody currently on it and no fallback.

**3. The deploy runbook** (Phase 3, your lane). Lower priority than the diagram, and
honestly if Bedrock stays blocked it matters less.

**4. The 30-second sanity check in §5**, if you have not already.

Feature freeze is **12 September 09:00**. After that it is bug fixes only.

---

# 7. Two small things back

**Every decision card now cites real evidence.** Every card the product had ever raised
carried `signal_id="unbacked"` and an excerpt reading *"Tool call cancel_subscription
with ['merchant', 'monthly_amount_minor', 'rationale', 'reason']"* — visible to the
user, under "why am I being asked this". Findings were getting their ids after the
whole graph finished, so nothing existed for a specialist's tool call to point at.
Fixed. Mentioning it because your `scenarios.json` scenario→signal-id mapping is what
will make the re-keyed version of this verifiable end to end.

**`set_reminder` fails for any household that is not `hh_demo`.** Your
`require_household` raises `UnknownHouseholdError`, correctly and by design — the
fixtures cover exactly one household. Not asking you to change it. Flagging it because
a Lane A test using an invented household id now gets a failed tool rather than a
successful one, which cost me ten minutes.

---

Thanks for the `as_of` field and for pushing on the empty-day problem. Both were right
and both were caught before they could embarrass us in front of a judge.
