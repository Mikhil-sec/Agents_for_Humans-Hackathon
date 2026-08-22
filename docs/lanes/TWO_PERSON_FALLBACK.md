# Two-person fallback

Read this only if the third teammate does not join. **Decide by 25 August 2026** — later than that and the reshuffle costs more than it saves.

---

## The principle

Lane C is not deleted, it is **split by nature of the work**: everything that touches the agent's inputs goes to A, everything that touches the user-facing surface goes to B.

## The reassignment

| Lane C work | Goes to | Why |
|---|---|---|
| Provider interface (`base.py`) | **A** | A is its only consumer. Owning it removes a coordination step entirely. |
| Mock providers | **A** | Same reason. |
| **Fixtures** | **B** | B is closest to how the data reads on screen, and B has more slack in week 1 while building UI shells. |
| Live Gmail / calendar / Plaid | **A** | Tool-shaped work. Cut entirely if time is short — see below. |
| DynamoDB, S3, IAM (CDK) | **B** | B already owns the API that reads them. |
| AgentCore deploy | **A** | Inseparable from the agent. |
| EventBridge schedule | **A** | Part of the agent's lifecycle. |
| SES digest email | **B** | It is a rendering job. |
| Amplify web deploy | **B** | Obviously. |
| Architecture diagram | **A** | A understands the agent internals best. |
| Demo video | **Both** | A narrates the agent, B narrates the product. |

Net effect: **A gains** the provider layer, AgentCore deploy, the schedule and the diagram. **B gains** fixtures, CDK, SES and the deploy pipeline. Roughly even, and neither person is blocked on the other more than before.

## What to cut, in this order

Two people cannot build everything in three weeks. Cut from the bottom up, and cut early — a decision made in week one is free, the same decision in week three costs whatever you already built.

**Cut first — no score impact:**

1. **Live providers entirely.** Ship mock-mode only. Be upfront in the README: *"Quiet Hours ships in simulation mode by default; the provider interface has live Gmail and Plaid implementations behind it, and we chose not to ship live credentials handling in the hackathon build."* Judges evaluate what runs. A flawless mock demo beats a broken live one, and the honesty reads as engineering judgement.
2. **AgentCore Gateway.** Nice architecture, not required. Runtime and Memory carry the AgentCore story on their own.
3. **The SSE live-run stream.** A polished polling refresh looks nearly identical on video.
4. **Dark mode.** Pick one theme and make it excellent.

**Cut only if you must — real score impact:**

5. **AgentCore Memory.** Fall back to DynamoDB for learned preferences. You lose an AgentCore talking point but keep the behaviour.
6. **The digest email.** The web app carries the product. Losing this weakens the "runs in the background" story, so keep it if you can.

**Never cut — these are the submission:**

- The interrupt → decision card → resume loop. This *is* the project.
- The policy engine and learned autonomy. This is the Creativity score.
- The autonomy trend chart. This is the demo's headline.
- The activity trail. Without it there is no trust story.
- Mock mode working from a clean clone. It is a hard rule requirement.
- The live demo link. It is explicitly worth points.
- The video, the diagram, the README, the licence.

## Revised timeline for two

| Dates | A | B |
|---|---|---|
| Aug 21–24 | Interrupt spike + provider interface | API skeleton + fixtures v1 |
| Aug 25–31 | Policy engine, graph, tools | Decision card, Today screen, CDK |
| Sept 1–7 | Full graph, policy learning, AgentCore | Activity, policies, insights chart |
| Sept 8–11 | Four-week replay, diagram, hardening | Amplify deploy, SES, polish |
| Sept 12–14 | Video (together), blog post | Video (together), README |
| Sept 15 | Submit | Submit |

## Process changes for a pair

- **Drop the two-approval rule on `/contracts`** — with two people it is just "both of you", which you would do anyway. Keep the `contract:` PR title and the announcement; the point is visibility, not ceremony.
- **Keep separate progress files.** Still the right call — they are how each person's AI assistant picks up context, and separate files still never conflict.
- **Keep CODEOWNERS**, with C's paths reassigned per the table above.
- **Add one 15-minute sync per day.** With three people you need structure; with two you need speed, and a short daily call replaces most of the written coordination.
