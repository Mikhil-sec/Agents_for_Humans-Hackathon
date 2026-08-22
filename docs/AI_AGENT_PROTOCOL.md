# AI Agent Protocol

**Every AI coding assistant working in this repository must follow this protocol.** It applies equally to Claude Code, Cursor, Copilot, Codex, Windsurf, Gemini CLI, Aider, and any other tool a team member uses.

The purpose of this document is narrow and important: **three people are working in parallel on a three-week deadline, each with their own AI assistant, and none of us can afford to spend a day resolving merge conflicts.**

---

## 1. Identify your lane before you edit anything

Ask the human you are working with which lane they own, or infer it from the current git branch prefix (`a/`, `b/`, `c/`).

| Lane | Owner | You may edit | You may read |
|---|---|---|---|
| **A** | Mikhil | `/agent`, `docs/lanes/LANE_A_AGENT.md`, `docs/status/PROGRESS_A.md` | everything |
| **B** | Teammate B | `/api`, `/web`, `docs/lanes/LANE_B_WEB.md`, `docs/status/PROGRESS_B.md` | everything |
| **C** | Teammate C | `/integrations`, `/infra`, `/fixtures`, `docs/lanes/LANE_C_INTEGRATIONS.md`, `docs/status/PROGRESS_C.md` | everything |

Reading any file in the repo is always allowed and encouraged. **Writing outside your lane is not.**

## 2. The five rules

### Rule 1 — Stay in your lane

Do not create, modify, delete, move or rename a file outside your lane's directories.

If completing the task genuinely requires a change elsewhere, **stop and tell the human**. Suggest the change in prose; do not make it. The human will coordinate with the lane owner.

This includes changes that feel harmless: fixing a typo in another lane's README, reformatting their Python, adding a missing type hint, "just" bumping a dependency. All of these produce merge conflicts on files someone else has open.

### Rule 2 — Never edit `/contracts` without a contract PR

`/contracts` holds the shared data shapes that all three lanes depend on. It is **frozen from 24 August 2026**.

If you believe a contract must change:

1. Stop.
2. Tell the human exactly which model needs to change and why.
3. The change ships as its own PR titled `contract: <what changed>`, touching nothing but `/contracts` and `docs/CONTRACTS.md`, approved by two lane owners.

A contract change silently bundled into a feature PR will break the other two lanes without warning. This is the single worst thing you can do in this repository.

### Rule 3 — Append to your progress file, never rewrite it

At the end of every working session, append a dated entry to `docs/status/PROGRESS_<YOUR LANE>.md`:

```markdown
## 2026-08-25 — session with <tool name>

**Done**
- Implemented `PolicyHook.evaluate()` with the four risk tiers
- Added 6 unit tests covering auto-approve and interrupt paths

**In progress**
- Graph wiring for the Negotiator node (branch `a/negotiator`)

**Blocked / needs a human**
- Need Teammate C to confirm the transaction fixture includes a duplicate-charge case

**Notes for the next session**
- `interrupt()` returns the raw string response; we parse it in `resume.py`, not in the hook
```

**Append at the bottom. Never reorder, rewrite, summarise or clean up earlier entries** — another session may be reading them, and rewrites conflict. The file growing long is fine and expected.

### Rule 4 — Verify before you claim

Do not report a task complete on the basis that the code "should" work.

- Python changes: run `pytest` in that lane.
- Web changes: run the dev server and open the page. Use the Playwright MCP server if you have it.
- Agent changes: run `make agent` in mock mode and confirm the run completes.
- Any change: confirm `make demo` still works from a clean state.

If you could not verify something, say so explicitly in your summary and in the progress file. An honest "untested" is far more useful to the team than a confident "done".

### Rule 5 — Do not commit or push

The humans handle all git operations in this project. You may stage nothing, commit nothing, and push nothing unless the human explicitly asks in that session.

You *may* freely run read-only git commands (`git status`, `git diff`, `git log`) to understand the state of the tree.

## 3. Starting a session

Do this before your first edit:

1. Read `AGENTS.md` at the repo root.
2. Read the `AGENTS.md` nearest to the code you are about to touch (e.g. `agent/AGENTS.md`).
3. Read your lane brief in `docs/lanes/`.
4. Read the last two entries of your `docs/status/PROGRESS_*.md`.
5. Skim `docs/status/DECISIONS.md` for anything decided since your last session.
6. Run `git status` and `git branch --show-current` to confirm you are on a lane branch, not `main`.

## 4. Ending a session

1. Run the lane's tests.
2. Append your progress entry (Rule 3).
3. Summarise for the human: what changed, what is verified, what is not, what needs a decision.
4. Leave the working tree in a state that compiles. Never end a session with a syntax error committed to a shared branch.

## 5. When the human asks for something outside your lane

Respond with something like:

> That change lives in `/web`, which is Lane B. I have not modified it. Here is exactly what needs to change so Teammate B (or their assistant) can apply it: ...

Then continue with whatever part of the task *is* in your lane. Do not block entirely on the cross-lane portion — deliver everything you can.

## 6. Building against contracts, not against other lanes

You should never need to wait for another lane. Every boundary is defined in `/contracts`, and every lane has a mock on the other side of it:

- **Lane B** develops against `api/app/fixtures_server.py`, which serves static contract-shaped JSON. B does not need the agent to exist.
- **Lane A** develops against `integrations`' mock providers, which read `/fixtures`. A does not need real Gmail.
- **Lane C** develops against the contract models directly, validating fixtures with `pytest`. C does not need the API or the agent.

If you find yourself blocked on another lane, you are probably reaching past a contract. Re-read `docs/CONTRACTS.md`.

## 7. Hallucination guardrails specific to this project

- **The Strands SDK moves fast.** Do not write Strands code from memory. Use the `context7` MCP server (`/websites/strandsagents`) or the official docs at `strandsagents.com`. Particular care with: `GraphBuilder`, `event.interrupt()`, `HookProvider`, `SessionManager`, `invocation_state`.
- **AgentCore is newer still.** Use the `aws-knowledge` MCP server for anything about AgentCore Runtime, Memory, Gateway, or its IAM requirements. The old `bedrock-agentcore-starter-toolkit` CLI is deprecated in favour of the AgentCore CLI (`npm install -g @aws/agentcore`) — do not follow tutorials that use the old one without checking.
- **Do not invent fixture data mid-task.** Fixtures are Lane C's and live in `/fixtures`. If you need a new scenario, request it.

## 8. Escalation

Anything that affects more than one lane goes in `docs/status/DECISIONS.md` as a new dated section appended at the bottom, and gets raised with the humans. Examples: adding a dependency all lanes will use, changing the risk tiers, changing the demo narrative, changing deployment targets.
