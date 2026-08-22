# Roadmap — 21 August to 15 September 2026

25 days. Three lanes. One rule above all others: **a working end-to-end slice by 31 August.**

---

## The one milestone that matters

**By Sunday 31 August, this must work:**

> A seeded email arrives → the agent triages it → the policy engine decides it needs a human → a decision card appears in the web app → the user taps Approve → the suspended Strands session resumes → the action completes → it appears in the activity trail.

Ugly is fine. Unstyled is fine. One scenario is fine. But it must run end to end.

Everything after 31 August is depth, polish and presentation. If the slice slips past the 31st, cut scope immediately using the order in `docs/lanes/TWO_PERSON_FALLBACK.md` — that list applies to a three-person team under pressure too.

---

## Phase 0 — Foundations (21–24 Aug)

| Lane | Deliverable |
|---|---|
| **A** | Interrupt spike proven: interrupt → persist → new process → resume → complete |
| **B** | FastAPI skeleton, every route returning fixture data |
| **C** | **Provider interface merged within 24 hours** (A is blocked on it), fixtures v1 |
| **All** | Repo public, MIT licence visible in the About section, contracts frozen 24 Aug |

**Exit criteria:** A can prove the interrupt mechanic works. B can serve a decision card over HTTP. C has mock providers Lane A can call.

**Highest risk in the whole project:** the interrupt spike. If `event.interrupt()` does not behave as we expect across process boundaries, we need to know on day 2 and redesign, not on day 18.

## Phase 1 — Vertical slice (25–31 Aug)

| Lane | Deliverable |
|---|---|
| **A** | Policy engine with tests; two real tools (one silent, one confirm); interrupt wired to the policy gate |
| **B** | Decision card component; Today screen with a genuinely good empty state; respond → resume endpoint |
| **C** | Full four-week fixture narrative; DynamoDB + S3 via CDK |

**Exit criteria: the milestone above, demonstrated to the whole team on a call.** Record a 60-second screen capture of it working — that is the insurance policy for the final video.

## Phase 2 — Depth (1–7 Sept)

| Lane | Deliverable |
|---|---|
| **A** | Full graph: triage → four specialists → brief. Policy learning from `APPROVE_ALWAYS`. AgentCore Runtime deployed. AgentCore Memory wired. |
| **B** | Activity trail, policies page, insights chart. Live backend replacing fixtures. SSE. |
| **C** | Live Gmail and calendar providers. EventBridge schedule. SES digest. |

**Exit criteria:** the four-week replay produces the autonomy curve, and the deployed agent is invokable on AgentCore.

## Phase 3 — Product polish and the live demo (8–11 Sept)

| Lane | Deliverable |
|---|---|
| **A** | Failure handling, prompt tuning, the replay script that generates the demo history |
| **B** | **Live demo deployed on Amplify.** Loading, error and edge states. Dark mode. Mobile. |
| **C** | Architecture diagram exported to `docs/assets/architecture.png`. Deploy runbook. |
| **All** | README. **Clean-machine test: clone the repo somewhere fresh and run `make demo`.** |

**Exit criteria:** a stranger can clone the repo and see it work, and the live URL is public.

The clean-machine test is not optional. Someone who has never run the project — ideally on a different OS — must do it. Every hackathon has entries that fail because they only ever ran on the author's laptop.

## Phase 4 — Presentation (12–14 Sept)

| Deliverable | Owner |
|---|---|
| Demo video, max 5 min, on YouTube/Vimeo, public | C leads, all contribute |
| builder.aws.com blog post — *"Agents for Humans"* in the title | A leads |
| Second blog post if time allows | B |
| Text description for the submission form | A |
| Final README pass | All |

**Feature freeze: 12 September, 09:00.** No new features after this, only bug fixes. Every hackathon team is tempted to add one more thing on the last day and every one that does regrets it.

The blog post is worth up to +0.6 on a 1–5 scale — proportionally the cheapest points available. Two posts at 0.2 each, plus a third if you have material. Write them from the progress files; the raw material is already there.

## Phase 5 — Submit (15 Sept)

Submit on the **morning** of the 15th, not the evening. Work through `docs/SUBMISSION_CHECKLIST.md` item by item.

---

## Standing commitments

**Daily**, each person appends to their own progress file. Two minutes. This is what lets each teammate's AI assistant resume with real context, and it is the source material for the blog posts.

**Every Monday, Wednesday, Friday** — 15-minute sync. Blockers only.

**Every PR** — small, single-lane, squash-merged. No branch lives longer than two days.

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Interrupt/resume doesn't work as expected | Medium | Spike it on day 1–2. If it fails, fall back to a shorter-lived approval queue polled by the agent — same UX, less elegant internals. |
| AgentCore deployment eats days | **High** | Timebox to two days. AgentCore is optional per the rules — a locally-run agent with a deployed web app still scores. Do not let it block the vertical slice. |
| Fixtures too thin, demo falls flat | Medium | C treats fixtures as a first-class deliverable, not an afterthought. Review them as a team on 31 Aug. |
| Third teammate doesn't join | Medium | `TWO_PERSON_FALLBACK.md`. **Decide by 25 Aug.** |
| Contract churn breaks lanes | Medium | Freeze 24 Aug, `contract:` PRs, CODEOWNERS. |
| Video left to the last day | **High** | Record the vertical slice on 31 Aug as insurance. Script written by 8 Sept. |
| Everyone builds, nobody writes the README | Medium | It is on the checklist and it is assigned. |

The two marked **High** are the ones that actually sink hackathon teams. Guard them.
