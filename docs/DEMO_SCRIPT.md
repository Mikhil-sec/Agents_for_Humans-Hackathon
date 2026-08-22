# Demo video script

**Hard limit: 5 minutes.** Target 4:15 — it leaves room and shorter videos hold attention.

Must cover, per the rules: (1) the problem, (2) who it's for, (3) why it matters, and a demonstration of the project working. No need to appear on camera. Upload to YouTube or Vimeo, set to **public**, and check the link in an incognito window before submitting.

**Record against mock mode.** Nothing in this video should depend on live credentials working on the day.

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

**1:25** — The Today screen. **Empty.** "Nothing needs you today."

> "This is what a normal morning looks like. Nothing needs me. Underneath: six things it handled on its own this week."

*Expand the activity trail. Show the silent actions with their reasoning.*

**1:50** — Trigger a run. Cards appear.

> "Today is different. It found three things."

**2:00** — **Card one, the gym.**

> "FitLife. Thirty-eight pounds a month. Last visit: March the twelfth. Eleven charges since. It's not just telling me — it's already drafted the cancellation, and it's showing me exactly why it thinks this: here's the last visit, here are the charges."

*Expand the evidence panel. Then click **"Cancel it — and always ask before renewing fitness"**.*

*Show the policy preview line before confirming.*

> "And notice — it's telling me the rule I'm about to create, in plain English, before I create it. It never grants itself permission quietly."

**2:25** — The card resolves. Activity trail updates. Savings counter moves to £456/yr.

> "Behind the scenes, that approval resumed an agent run that had been suspended since seven this morning — sitting durably in S3, costing nothing, waiting for me."

## 2:40–3:20 — The mechanic that makes it different

*Screen: the insights chart. Two lines over four weeks.*

> "Here's the part I actually care about.
>
> Week one, it asked me about nine things — it didn't know me yet. Week four: two. Meanwhile the number of things it handled on its own went from four to twenty-six.
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
> It's deployed on AgentCore Runtime, with AgentCore Memory holding what it's learned about the household."

## 4:00–4:15 — Close

*Screen: back to the empty Today screen.*

> "Most agents ask you about everything. Quiet Hours earns the right to stop asking.
>
> It's open source, it runs from a clean clone with no credentials, and there's a live demo linked below."

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
