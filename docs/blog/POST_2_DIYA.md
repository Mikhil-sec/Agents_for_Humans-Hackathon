# Agents for Humans: when success looks like an empty screen

*Draft for builder.aws.com. Second of our two posts — Mikhil's covers the agent
and the interrupt mechanic; this one is the interface and the API behind it.
Everything here is from Quiet Hours, our entry to the AWS **Agents for Humans**
hackathon, Everyday Agents track.*

---

Most agent interfaces are a chat box. You type, it thinks, it answers. The whole
surface is built around the assumption that you are sitting there.

We built the opposite. **Quiet Hours** is an agent that handles household
admin — bills, renewals, price rises, free trials about to convert — and its
entire value proposition is that it does not talk to you. It runs on a schedule.
Most days it does four or five things and tells you about none of them. It
interrupts you only when there is a decision that is genuinely yours to make:
cancelling a service, spending money, sending a message on your behalf.

That produced a design problem I did not expect, and it turned out to be the most
interesting part of the build:

> **If the product is working, the screen is empty. So how does a user tell
> "everything is fine" apart from "everything is broken"?**

A chat app never has this problem. An empty chat is obviously an empty chat. But
our best-case screenshot — the one that communicates the whole idea — is a page
that says *"Nothing needs you today."* And a page that says nothing at all,
because the API is down, looks almost exactly the same.

Nearly every interesting decision in the front end came out of that one question.

## Empty, loading and broken must look nothing alike

The lazy version of this screen is a spinner that resolves into nothing. We
banned it. Each of the three states got its own deliberate, distinct treatment:

- **Loading** is a skeleton with the *shape* of a decision card — so you can see
  something is coming, and roughly what.
- **Empty** is a quiet tick, a sentence, and one line of evidence that the agent
  has been working: *"Quiet Hours handled 19 things without asking and saved you
  £164.20 this month."* Reassurance, not celebration. No confetti, no
  "You're all caught up!".
- **Broken** names the failure and says what happens next.

That last one is where most of the work went. Our API returns a stable
machine-readable code on every error, and the web app switches on the code rather
than on an HTTP status or — worse — the wording of a message:

```ts
export function explain(error: QuietHoursError): { title: string; detail: string } {
  switch (error.code) {
    case 'offline':
      return {
        title: "You're offline",
        detail:
          'Quiet Hours keeps working while you are away — nothing is lost. ' +
          'This page will fill in when the connection is back.',
      };
    case 'agent_unavailable':
      return {
        title: 'The agent is not reachable',
        detail:
          'Your answer was saved and the run will pick it up when the agent ' +
          'is back. Nothing was lost.',
      };
    // ...
    default:
      return { title: 'That did not load', detail: error.message };
  }
}
```

Every branch names the thing the user can actually do next, and several of them
exist to say *nothing was lost*. In a product that touches someone's bank account,
"something went wrong" is worse than no error message at all — it invites the user
to imagine the worst specific thing.

Note the `default` branch. The API can add a code we have never seen; an
unrecognised one degrades to a sentence rather than throwing. Same rule applies to
every `switch` on a shared enum in the codebase, because the agent lane could add
a new finding type mid-build and we did not want that to white-screen the
interface.

## The failure mode nobody would ever notice

Here is the one that genuinely worried me. Suppose we ship a front end that
expects one data shape and the API starts serving another. In a normal product
you would see it instantly — the page fills with `undefined`, a list renders
empty, something visibly breaks.

In our product, a broken deploy renders as a calm, quiet, empty inbox. Which is
exactly what a *good day* looks like. The user would sit there being told nothing
needs them while their trial converted and their bill went up.

So every API response carries the contract version, in the body and in a header,
and the web app compares it against a value compiled in at build time:

```ts
export function isMajorMismatch(server: string | null): boolean {
  if (!server) return false;
  return server.split('.')[0] !== CONTRACT_VERSION.split('.')[0];
}
```

Major only. A minor bump means someone added a field, which every consumer
tolerates. A major difference means a shape changed underneath a deploy, and the
app shows a banner saying the page cannot be trusted.

It is about fifteen lines of code and it has never fired in anger. I would ship it
again immediately. **The cost of a silent failure is proportional to how quiet the
product is by design.**

## Building the whole interface before the agent existed

Three of us built this in three weeks, in parallel: one on the agent, one on the
web app and API, one on integrations and infrastructure. The web app could not
wait for the agent to produce its first real decision card.

So the API has a seam at the store, not at the API:

```python
class Backend(Protocol):
    """Read and write access to one household's Quiet Hours state."""

    def list_decisions(self, *, status: str | None = None) -> list[DecisionCard]: ...
    def get_decision(self, decision_id: str) -> DecisionCard | None: ...
    def respond(self, card: DecisionCard, response: DecisionResponse) -> tuple[str, str]: ...
    # ...
```

Two implementations. One reads DynamoDB and resumes a suspended agent session. The
other reads static JSON fixtures from disk. `QH_BACKEND=fixtures` is the default,
it needs zero credentials, and it is what a judge gets when they run `make demo`.

The important detail is that **both return the same validated domain models**, not
dicts. Everything above the seam — routers, pagination, the digest email renderer —
is written once and has no idea which backend it is talking to.

The second important detail: the fixtures backend is a stub of the *store*, not of
the product. Answering a card genuinely resolves it, genuinely writes an audit
entry, and genuinely creates the policy the button promised — in memory, lost on
restart, which is the correct blast radius for a mock. A demo where the buttons do
nothing is worse than no demo, because the reviewer finds out by clicking.

Everything loaded from fixtures is parsed through the same frozen Pydantic models
the live path uses. When another lane regenerated the fixture set — four times in
one day, at one point — a shape that had drifted failed at load with the field name
in the error, rather than at render time in front of a judge.

## Two smaller decisions I would defend

**The wire format is snake_case, all the way into the React components.** No
camelCase mapping layer. Our shared contracts are defined once in Python and
mirrored in TypeScript, and every mapping layer is a place where the two can
silently disagree. `card.why_asking` looks mildly wrong in a `.tsx` file for about
a day, and then you stop noticing, and you have deleted an entire category of bug.

**The live-progress stream is deliberately *not* a contract type.** When you hit
"Check now", the run narrates itself over Server-Sent Events. Those frames are the
only payload in the app that does not come from our shared contracts, and that is
on purpose: the contracts describe *stored state*, and nothing persists a progress
frame. Where the stream does need to carry stored state — the finished run, the
decisions it raised — it sends the contract model whole rather than a paraphrase
of it.

It is a small distinction, and it stopped the contract from accumulating
transport-shaped fields that nothing ever stored.

## The screen that justifies the whole thing

One more, because it is the heart of the product rather than the plumbing.

Quiet Hours gets quieter over time: you can answer a decision with "always", and it
writes a rule so it stops asking about that class of thing. Over four simulated
weeks our interrupt rate falls from four decisions a week to one, while the number
of things handled silently rises.

Granting an agent standing permission to spend your money is a serious thing to do
by tapping a button. So the button is never allowed to be the first time you see
what you are agreeing to. The agent sends the rule it would create, in plain
English, and we render it *above* the buttons:

> **Answering "always" creates a rule**
> Always do this: Always cancel subscription for PhotoCloud up to £4.99
> *You can revoke any rule from the Rules page. Quiet Hours will never write one
> you have not read.*

The rule is shown verbatim, exactly as the agent phrased it, and stored verbatim —
the Rules page shows the user the same words they agreed to, not a reconstruction
from a scope/merchant/amount triple. There is a page listing every rule with how
many times it has fired and a one-click revoke, and revoking is deliberately
easier than granting.

Two other things sit behind that, both enforced in ordinary code rather than in a
prompt: the policy engine that applies these rules contains no model call, and no
rule can ever auto-approve something irreversible like disputing a charge or
closing an account. An `if` statement cannot be argued out of a safety rule.

## What I would tell someone starting one of these

If you are building an interface for an agent that works while nobody is watching,
the interesting problems are not the ones you get in a chat UI.

1. **Design the empty state first.** It is the state your users will see most
   often, and if you design it last it will look like an afterthought — because it
   will be one.
2. **Make "nothing happened" and "something broke" impossible to confuse.** The
   quieter your product, the more expensive a silent failure is.
3. **Put the seam at the store, not at the API.** It is what lets the interface
   exist before the agent does, and it is what a reviewer runs with no credentials.
4. **Never let a button be the first time someone sees what they are agreeing to.**
   If an agent is going to act on its own, the user has to be able to read the rule
   before granting it, and revoke it afterwards in one click.

The whole thing is open source, runs from a clean clone with no AWS account and no
credentials, and the four-week autonomy curve is real data from actual runs rather
than a drawn graph.

*Built with Strands Agents, Amazon Bedrock, Bedrock AgentCore, FastAPI and
Next.js. Repository: <https://github.com/Mikhil-sec/Agents_for_Humans-Hackathon>*

---

## Notes before publishing — delete this section

- [ ] Confirm Mikhil's post does not already cover the policy-preview screen; if it
      does, cut the "screen that justifies the whole thing" section down to a link.
- [ ] Check the title requirement — the hackathon rules ask for *"Agents for
      Humans"* in the title, which this has.
- [ ] Swap the repo link for the live demo link if Yorvan gets one up.
- [ ] Screenshots worth including: the empty state ("Nothing needs you today"), the
      decision card with the rule preview, and the autonomy chart. All three exist
      in light and dark.
- [ ] Word count is about 1,400. builder.aws.com has no hard limit but shorter
      reads better — the "two smaller decisions" section is the first to cut.
