@AGENTS.md

# Claude Code — supplementary notes

Everything binding lives in `AGENTS.md`, imported above. This file holds only the extras that are specific to Claude Code.

## Before you start

1. Read `docs/AI_AGENT_PROTOCOL.md`. It defines which files you may edit.
2. Read the lane brief for the directory you are working in (`docs/lanes/LANE_*.md`).
3. Read your lane's progress file to see where the last session left off.

## MCP servers

`.mcp.json` is committed at the repo root. Approve the servers when prompted. Notably:

- **aws-knowledge** — managed remote server, no account needed. Use it for anything Bedrock / AgentCore / IAM related rather than relying on training data.
- **context7** — use for Strands SDK, Next.js, FastAPI and Pydantic APIs. The Strands SDK moves fast; do not write Strands code from memory.
- **playwright** — use to actually open the web app and verify a UI change rather than assuming it renders.

## Working style for this repo

- Prefer small, single-lane PRs over large ones. We are three people on a three-week deadline; long-lived branches will hurt.
- When you finish a unit of work, append a dated entry to your lane's progress file before you consider the task complete.
- If a task would require editing outside your lane, stop and surface it. Do not "helpfully" refactor another lane's code.
- Do not commit or push unless explicitly asked — the humans handle git in this project.

## Hackathon context

Deadline **15 Sept 2026**. Judged on Technical Implementation, Design, Potential Impact, Creativity and Presentation. `docs/SUBMISSION_CHECKLIST.md` tracks every deliverable — check it before claiming any milestone is complete.
