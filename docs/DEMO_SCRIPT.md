# Demo video script

**Hard limit: 5 minutes.** Target 4:15 — it leaves room and shorter videos hold attention.

Must cover, per the rules: (1) the problem, (2) who it's for, (3) why it matters, and a demonstration of the project working. No need to appear on camera. Upload to YouTube or Vimeo, set to **public**, and check the link in an incognito window before submitting.

**Record against mock mode.** Nothing in this video should depend on live credentials working on the day.

## Before you hit record

- **Restart the demo first.** Answering the card is a one-way flip in the running store, so a second take needs a fresh start. `.local\stop-demo.ps1` then `.local\run-demo.ps1` puts the FitLife card back as pending — verified 12 September.
- **Do not press "Check now" on camera.** It does nothing visible: a fixtures-mode run completes immediately, finds nothing new, and the page does not change. The script no longer uses it.
- **Don't narrate dates on the Activity page.** The trail stamps every entry with the moment the fixtures were exported, so all twenty-six sit under one day heading. The *Insights* chart is the screen that carries the four-week axis correctly (1, 8, 15, 22 Aug) — make the time argument there.

---

## 0:00–0:35 — The problem

*Screen: a real-looking inbox, scrolling. Renewal notices, price-change emails, bill reminders.*

> "Last year I paid £456 for a gym I stopped going to in March.
>
> Not because I couldn't afford to cancel it. Because cancelling it was a four-minute job, and four-minute jobs are exactly the ones that never get done.
>
> The average household runs about twelve subscriptions and eight recurring bills. Each one occasionally needs something: a price goes up, a trial converts, a charge lands twice. Individually, minor. Together, hours a month — and the real cost isn't the time. It's the money you keep paying for things you don't use."

**Note:** open with the specific number. £456 for a forgotten gym is concrete and immediately recognisable. Do not open with "in today's fast-paced world".

## 0:35–1:00 — Who it's for, and why the obvious answer doesn't work

*Screen: a phone home screen full of app icons.*

> "The usual answer is an app. A budgeting app, a subscription tracker. But those just move the work — now you have to remember to open the thing that reminds you.
>
> This is built for people with no slack in their week. New parents. Carers. Anyone working two jobs. People for whom 'just check your statements each month' was never going to happen.
>
> So we built an agent that does the checking, does the work, and only interrupts you when there's a decision only you can make."

## 1:00–1:25 — What it is

*Screen: the architecture diagram, animated along the flow.*

> "Quiet Hours is an agent built with the Strands Agents SDK, running on Amazon Bedrock AgentCore.
>
> Every morning it wakes on a schedule. It reads the inbox, the transaction feed and the calendar. A multi-agent graph triages what it finds — a specialist for bills, one for cancellations and disputes, one for scheduling.
>
> Then every single action it wants to take passes through a policy gate. Low-risk and reversible? It just does it, and logs it. Spends money, sends a message, cancels a service? It stops and asks."

## 1:25–2:40 — The demo *(the most important 75 seconds)*

*Screen: live product. Do not narrate the UI — narrate what happened.*

**1:25** — The Today screen, as the agent left it at seven this morning. One card. The header reads *"One thing needs you."*

> "This is the whole product. Not a feed, not a digest I have to read — one thing. Underneath it, nineteen things it handled this month without asking me once."

*Scroll the "handled without asking" list. Let two or three sit on screen — the bills it paid under rules already granted.*

**1:50** — Back up to the card.

> "One decision, and it waited for me to be awake to ask it."

**2:00** — **The card.**

> "FitLife. Thirty-eight pounds a month — and it renews in six days at four hundred and fifty-six pounds for the year. For a gym I haven't been to since March.
>
> It isn't just flagging it. The cancellation is ready to go, and it's showing me exactly where it got this — the renewal notice, in the gym's own words."

*Expand the evidence panel and hold on it. Then click **"Always do this"**.*

*Hold on the policy preview line before it resolves.*

> "And notice — it tells me the rule I'm about to create, in plain English, before I create it: always cancel FitLife, up to thirty-eight pounds. It never grants itself permission quietly."

**2:25** — The card resolves and the screen goes to the empty state: *"Nothing needs you today."*

> "And that's what I actually want to see. Behind it, that approval resumed an agent run that had been suspended since seven this morning — parked durably, costing nothing, waiting for me."

## 2:40–3:20 — The mechanic that makes it different

*Screen: the insights chart. Two lines over four weeks.*

> "Here's the part I actually care about.
>
> Week one, it asked me about four things — it didn't know me yet. Week four: one. Meanwhile the number it handled on its own went from three a week to six.
>
> Every time I approve something, I can turn that into a rule. The policy engine — which is deterministic code, not a model — applies those rules on every future run. So the agent gets quieter as it earns trust.
>
> And I can see every rule I've granted, how often it's fired, and revoke any of them in one click."

*Show the policies page. Revoke one.*

> "It never learns to do something I didn't explicitly allow. And some things — disputing a charge, closing an account — no rule can ever auto-approve. That's enforced in code, not in a prompt."

## 3:20–4:00 — How it's built

*Screen: code, briefly. `hooks.py`, then the graph.*

> "Strands gave us three things that made this possible.
>
> `GraphBuilder`, for the multi-agent triage pipeline.
>
> Hooks on `BeforeToolCallEvent` — that's where the policy gate lives, so *every* tool call is governed, including ones the model invents.
>
> And interrupts with durable sessions. When the agent hits a decision it shouldn't make alone, it calls `interrupt`, the process exits, and the run resumes days later exactly where it stopped. That's what lets an agent run at 7am while you're asleep and still ask you a question.
>
> It's built for AgentCore Runtime, with AgentCore Memory holding what it's learned about the household. And everything you've just watched runs from a clean clone with no AWS credentials at all — the whole loop, interrupt and resume included."

**Do not say "it's deployed on AgentCore".** Nothing is deployed. Bedrock has returned `ValidationException: Operation not allowed` on this account for every model since 26 August — Amazon's own Nova included — and support case 178815493800207 is still unassigned. Saying it on camera would be a factual misstatement to judges about a submission. The zero-credential claim is the better line anyway: it is unusual, and a judge can verify it in two minutes.

## 4:00–4:15 — Close

*Screen: the empty Today screen you landed on at 2:25 — no need to navigate anywhere.*

> "Most agents ask you about everything. Quiet Hours earns the right to stop asking.
>
> It's open source, it runs from a clean clone with no credentials, and there's a live demo linked below."

**The live demo line is safe to say.** `https://mikhil-sec.github.io/Agents_for_Humans-Hackathon/` was checked on 12 September: HTTP 200, loads for a logged-out stranger, all four screens, answering a card and revoking a rule both work. Re-check it in an incognito window on the day before uploading.

---

## Production notes

- **Record 1440p or higher**, then downscale. Text must be readable when a judge watches in a small window.
- **Increase the browser font size** before recording.
- **Cut every loading spinner.** If a run takes twelve seconds, cut to the result.
- **Voiceover recorded separately** from the screen capture and laid over it. Trying to narrate live while clicking produces stumbles and dead air.
- **No background music**, or very quiet. It competes with the voice and adds nothing.
- **Watch it once at 1.5×.** If it still makes sense, the pacing is right.

## What to cut if it runs long

In this order: the code section (3:20–4:00) down to 20 seconds; the "who it's for" section down to one line; the architecture walk-through down to a single held frame.

**Never cut:** the £456 opening, the empty-state screen, the decision card with its evidence, or the autonomy chart. Those four beats are the entire pitch.
