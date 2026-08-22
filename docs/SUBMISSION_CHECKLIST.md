# Submission checklist

Work through this on **15 September, in the morning**. Not the evening.

Every line is a literal requirement from the rules. A submission that fails one of these can be disqualified regardless of how good the project is — most commonly the licence not being visible in the About section, or the video not being public.

---

## Hard requirements

- [ ] **Public code repository URL** (GitHub) — open it in an incognito window to confirm it is genuinely public
- [ ] **MIT or Apache licence file** in the repo
- [ ] **Licence visible in the GitHub About section** — GitHub must detect it. Check the right-hand sidebar of the repo page says "MIT license". If it does not, the `LICENSE` file is malformed or misnamed.
- [ ] **README** with setup instructions
- [ ] **All source code, assets and setup instructions** needed to run the project are in the repo
- [ ] **Architecture diagram** — labelled with: user interface, Strands agent + agentic loop, tools & integrations, AWS services, output
- [ ] **Demo video, max 5 minutes**, uploaded to YouTube or Vimeo, **set to public**, link checked in an incognito window
- [ ] Video demonstrates the working project
- [ ] Video pitch covers: (1) the problem, (2) who it's for, (3) why it matters
- [ ] **Text description** of features and functionality, written for the submission form
- [ ] **AWS Builder ID** — have it to hand; create it in advance if you don't have one
- [ ] Track selected: **Everyday Agents**
- [ ] Any third-party SDK, API or dataset we use, we are authorised to use under its terms
- [ ] Any pre-existing code incorporated into the project is disclosed

## Strongly recommended (explicit scoring impact)

- [ ] **Live demo link** — the rules state this improves the Technical Implementation score
- [ ] **AgentCore deployment** — same
- [ ] **builder.aws.com blog post** with *"Agents for Humans"* in the title, published publicly before the deadline (+0.2)
- [ ] Second blog post (+0.2)
- [ ] Third blog post (+0.2, max +0.6 total)

## Quality gate — do this before submitting

- [ ] **Clean-machine test**: clone the public repo into a fresh directory on a machine that has never run this project, follow the README exactly, confirm `make demo` works. Ideally on a different OS to the one it was built on.
- [ ] `make test` passes on `main`
- [ ] No secrets, tokens, keys or `.env` files committed — `git log -p | grep -iE "api[_-]?key|secret|password|BEGIN.*PRIVATE"`
- [ ] Every link in the README resolves
- [ ] The architecture diagram image actually renders on the GitHub page
- [ ] Live demo URL loads for a logged-out stranger
- [ ] Repo has a description and topics set (`strands-agents`, `aws`, `bedrock`, `agentcore`, `ai-agents`)
- [ ] `main` is green and nothing is left on an unmerged branch

## Judging criteria — a final honest self-assessment

Score yourselves out of 5 the day before. Anything at 3 or below, ask whether an hour would fix it.

| Criterion | What they're asking | Our evidence | Score |
|---|---|---|---|
| **Technical Implementation** | Thorough, skilful use of Strands; genuine effort; non-trivial and working | Graph orchestration, hooks on `BeforeToolCallEvent`, durable interrupts with cross-process resume, structured output, MCP tools, AgentCore Runtime + Memory, live demo | /5 |
| **Design** | A complete, coherent product — not a proof of concept | Decision inbox, empty state, activity trail, policies page, insights chart, digest email, dark mode, mobile | /5 |
| **Potential Impact** | A credible, specific case for a real problem and a real audience | £456 forgotten gym; named audience (people with no slack); demonstrated savings; the solution visibly does the thing | /5 |
| **Creativity & Originality** | Creative, non-obvious use of Strands; real understanding of the problem space | Earned autonomy — the interrupt rate provably falls; the interrupt *is* the product, not an edge case | /5 |
| **Presentation** | Clear end-to-end demo; clear pitch; easy to follow | 4:15 video following `DEMO_SCRIPT.md` | /5 |

## The text description

Draft it here, then paste into the form. Keep it tight — judges read a lot of these.

> **Quiet Hours** is an autonomous agent that handles the recurring administrative busywork of running a household — bills, subscriptions, price rises, expiring trials, duplicate charges — and interrupts you only when there is a decision only you can make.
>
> **The problem.** The average household runs about twelve subscriptions and eight recurring bills. Each occasionally needs a four-minute job done: cancel this, query that, reschedule the other. Four-minute jobs are exactly the ones that never get done, and the cost is not the time — it is the £456 a year you keep paying for a gym you stopped using in March.
>
> **Who it's for.** People with no slack in their week: new parents, carers, anyone working two jobs. The people for whom "just review your statements each month" was never a realistic instruction.
>
> **How it works.** Quiet Hours runs on a schedule with no app to open. A Strands Agents multi-agent graph ingests email, transactions and calendar events, triages them into findings, and routes them to specialists that analyse bills, draft cancellations and disputes, and handle scheduling. Every action the agent proposes passes through a deterministic policy gate implemented as a Strands hook on `BeforeToolCallEvent`. Reversible, low-risk actions execute silently and are logged with their reasoning. Anything that spends money, sends a message or cancels a service triggers a Strands interrupt: the run suspends durably, the process exits, and a decision card appears in the web app. When you answer — hours or days later — the agent resumes the same session exactly where it stopped and finishes the job.
>
> **What makes it different.** Autonomy is earned, not assumed. Approving an action can create a policy, shown to you in plain English before you grant it. The policy engine — deliberately deterministic code rather than a model — then handles that class of action silently on future runs. Over four weeks the agent's interrupt rate falls from about nine decisions a week to two, while the number of things it handles on its own rises from four to twenty-six. Every policy is listed, counted and revocable in one click, and irreversible actions such as disputing a charge can never be auto-approved by any policy.
>
> **Built with** Strands Agents SDK (`GraphBuilder`, hooks, interrupts, durable sessions, structured output, MCP tools), Amazon Bedrock (Claude Sonnet 4.5), Bedrock AgentCore Runtime and Memory, Lambda, DynamoDB, S3, EventBridge, SES and Amplify.
>
> **Safety.** Even in live mode the agent creates email drafts and scheduled payment requests — it has no code path that sends mail or moves money unattended. The project ships in simulation mode by default and runs from a clean clone with no credentials.

## Assignments

| Deliverable | Owner | Due |
|---|---|---|
| Demo video | C (all contribute) | 14 Sept |
| Architecture diagram | C | 11 Sept |
| README | A | 11 Sept |
| Live demo deployed | B | 11 Sept |
| Blog post 1 | A | 13 Sept |
| Blog post 2 | B | 14 Sept |
| Text description | A | 14 Sept |
| Clean-machine test | Whoever built least of it | 12 Sept |
| Final submission | Mikhil | **15 Sept, morning** |
