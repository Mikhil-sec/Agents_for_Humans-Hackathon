# Lane B → Lane A and Lane C — 11 September

From Diya.

Answering Mikhil's `FOR_DIYA.md` of 10 September. Three of your four asks are done,
the fourth is blocked on something only one of you can unblock, and I found one
bug in the `Makefile` that I have not touched because it is not my file.

**I have merged `miks-branch` into `main` locally.** Details and the one thing I
want a second opinion on are in section 4.

---

## 1. `make demo` works. I tested it properly.

`make` was not installed on my machine either, so I installed GNU Make 4.4.1
(`winget install ezwinports.make`) rather than eyeball the recipes. Fresh
`git clone` into an empty directory, into a throwaway venv so my working tree's
editable installs were not repointed at a temp path.

| Step | Result |
|---|---|
| `make install` | works — 4m21s (four pip installs + `npm install`, 323 packages) |
| `make demo` | works — one command, API on :8000 and web on :3000 |
| **One Ctrl+C stops both** | **works** |
| Four-week data behind it | correct — 1/8/15/22 Aug, savings populated, brief headline right |
| Insights chart | four evenly spaced weekly points; the 7 Sept gap is gone |

**On the Ctrl+C result, because the method matters.** Killing the parent process is
*not* the same test and gives a false failure: on Windows it orphans the Next dev
server still holding :3000. I raised a real `CTRL_C_EVENT` with
`GenerateConsoleCtrlEvent` against the demo's console, which is what the key
actually does. Both processes exited and both ports released. Your `$(MAKE) -j2`
is correctly wired, Mikhil.

## 2. Mikhil — one real bug in the `api` target. Yours to fix, one word.

`make demo` **fails from `cmd.exe` or PowerShell.** The web app starts, the API
dies immediately, and every screen renders its error state:

```
cd api && QH_PROVIDER_MODE=mock uvicorn main:app --reload --port 8000
'QH_PROVIDER_MODE' is not recognized as an internal or external command
make: *** [Makefile:72: api] Error 1
```

`VAR=value command` is POSIX syntax. GNU Make on Windows uses `cmd.exe` as its
shell unless `sh.exe` is on PATH, so this works from Git Bash — which is how I
tested it, and how it behaves on macOS and Linux — and fails from a native Windows
shell.

**The fix is a deletion, not a rewrite.** `QH_PROVIDER_MODE` is not read anywhere
in `/api` — I grepped the whole directory. The API reads `QH_BACKEND`, which
already defaults to `fixtures`:

```python
# api/app/config.py
BACKEND = os.environ.get("QH_BACKEND", "fixtures").strip().lower()
```

So:

```make
api:
	cd api && uvicorn main:app --reload --port 8000
```

Portable, and functionally identical. I have not made the change because the
`Makefile` is yours — say the word and I will, or it is thirty seconds for you.

How much this matters is your call. Every judge on macOS or Linux is unaffected.
A judge on Windows who runs `make demo` from PowerShell sees a broken product.

## 3. Done on my side since your note

- **The gitlink.** `git rm --cached Agents_for_Humans-Hackathon`, committed. I also
  deleted the physical duplicate clone after checking it was safe — clean status,
  no stash, no unpushed commits, sitting on `1f8acff`, which is an ancestor of
  `main`. Confirmed absent from a fresh clone.
- **The favicon.** `web/app/favicon.ico` plus `apple-icon.png`, generated from the
  clock mark in the header. Multi-resolution ICO; the 16px frame is drawn with a
  heavier ring because the hairline version turns to grey mush at that size.
  `/` and `/insights` now report **zero console errors**.
- **Mobile.** Nobody had checked it and the checklist claims it under Design. Two
  real defects at 390px, both now fixed: the header wordmark wrapped to two lines
  and made the bar look broken, and the autonomy chart scaled its 720-wide viewBox
  down until the axis labels rendered at about 5px — the headline visual,
  illegible on a phone. The chart now scrolls horizontally at a readable size
  instead of shrinking. Desktop is unchanged. Verified no horizontal overflow on
  any of the four screens under real mobile emulation.
- **`estimated_annual_savings`.** Taken, thank you. Insights now shows it as a rate
  under the realised figure — *"£411.90 saved so far / worth £1,055.76 a year at
  this rate"*. I kept them apart on purpose: "saved" stays money that actually
  moved, and the projection is labelled as a projection. It reads `null` while a
  run's cancellation is pending, so it does move when the user answers the card,
  which is the beat you wanted for the video.
- **`web/app/layout.js`.** An untracked `create-next-app` default root layout
  (`title: 'Next.js'`) was sitting next to our real `layout.tsx`. Deleted. Never
  committed, but two root layouts in one App Router segment is ambiguous at best.

## 4. I merged `miks-branch` into `main`

Locally, not pushed — I wanted you to see this section first.

`origin/main` was still `14a7c52`. **Everything that makes `make demo` work was
only on `miks-branch`**: the fixed `demo` target, the four-run `runs.json` with
savings, the corrected brief headline, the weekly run dates. A judge cloning
`main` today got the version that prints three lines and exits.

The merge was clean — no conflicts, and it touches nothing in `/web` or `/api`.
The gitlink stays removed: `miks-branch` still carried it, `main`'s deletion wins.

After merging I re-verified from a fresh clone of the merged `main`: 43 API tests
pass against the regenerated fixtures, `make install` and `make demo` both work,
and the four-week chart renders correctly.

**What I want from you before I push:** just a nod. Mikhil, your note asked us to
branch and PR from here and this is a merge straight onto `main`, which is exactly
what you asked us to stop doing. I think it is the right call four days out — the
alternative is that `main` stays broken while a PR waits — but it is your process
point and I would rather you agreed than found out.

## 5. Yorvan — the live demo link is more achievable than we thought

Mikhil's note says a deployed app would have no working agent behind it while
Bedrock is returning `ValidationException`, so it is not worth much. That is true
of the *live* path. It is not true of the judged path.

**Mock mode needs no Bedrock at all.** `QH_BACKEND=fixtures` needs zero
credentials and never calls the agent, and the web build never contacts the API —
I verified that by stopping the API and running `npm run build`, which succeeded.
So a live demo link showing exactly what `make demo` shows is achievable **while
Bedrock is still broken**, and it is honest as long as the README says the hosted
demo runs in mock mode, which it already says about the whole project.

What it needs:

1. **The API hosted somewhere** with `QH_BACKEND=fixtures`. Step 4 of your
   `DEPLOY.md`. No Bedrock, no DynamoDB, no AgentCore, no secrets.
2. **`QH_CORS_ORIGINS`** set to the Amplify origin, or every screen renders its
   error state. Easy to forget; it is the first thing to check if the deployed app
   looks broken.
3. **Amplify pointed at the repo.** `web/amplify.yml` is committed and ready — I
   wrote it but I have not been able to run it, because there is no AWS CLI and no
   credentials on my machine. It encodes the two things Amplify's auto-detection
   gets wrong here: the app is not at the repo root (`appRoot: web`), and the build
   reads `contracts/typescript/index.ts` from *above* `appRoot` via
   `experimental.externalDir`, so the checkout must not be narrowed to `web/`.
   Set `NEXT_PUBLIC_API_URL` in the console, not in the file.

That is closer to ten minutes than to a day. If it still does not work, we ship
without it and say so — you are both right that it is a bonus item and mock mode
is the judged path.

## 6. What I still need from you

| # | Who | What | Why it matters |
|---|---|---|---|
| 1 | Mikhil | A nod on the `main` merge in section 4 | Process; I would rather ask than assume |
| 2 | Mikhil | Drop `QH_PROVIDER_MODE=mock` from the `api` target | `make demo` is broken on native Windows shells |
| 3 | Yorvan | Host the API in fixtures mode, set `QH_CORS_ORIGINS` | Unblocks the live demo link, no Bedrock needed |
| 4 | Either | AWS credentials, or run the Amplify connect yourselves | I cannot deploy from here |
| 5 | Yorvan | `docs/assets/architecture.png` | Hard requirement, still does not exist |

Nothing here blocks the submission. Mock mode works from a clean clone with no
credentials, which is the rule that actually matters.

## 7. Where Lane B is

Done and verified: four screens, the API on a store seam with both backends, the
digest email, the SSE run stream, dark mode, mobile, the favicon, 43 tests, lint
clean, and a production build that needs neither credentials nor a running API.

Not done: no component or end-to-end test suite in `/web` — the screens have been
driven by hand in a real browser, which is not the same thing. And the `live`
DynamoDB backend has still never touched real AWS, for the same reason as
everything else in this document.

If either of you wants the second `builder.aws.com` post written, say so — the raw
material is already in `PROGRESS_B.md` (the backend abstraction, why the SSE frames
are deliberately not contract types, why the wire format is snake_case) and I would
rather write it than have it not happen.
