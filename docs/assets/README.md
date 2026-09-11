# Assets

| File | Owner | Status |
|---|---|---|
| `architecture.png` | Lane C | **Required deliverable** — done |
| `architecture.svg` | Lane C | Source file, committed alongside the export |
| `screenshot-today.png` | Lane B | For the README |
| `screenshot-insights.png` | Lane B | The autonomy chart |

## The architecture diagram

A hard submission requirement. It must clearly label:

- **User input / interface** — the web app and the digest email
- **Strands Agents** — the core agent and its loop (model → tools → reasoning → response)
- **Tools & integrations** — email, transactions, calendar, DuckDuckGo MCP, Playwright MCP
- **AWS services** — Bedrock, AgentCore Runtime + Memory, Lambda, DynamoDB, S3, EventBridge, SES, Amplify
- **Output** — decision cards, the activity trail, the digest

`docs/ARCHITECTURE.md` has an ASCII version to work from.

**Source format: SVG, not draw.io.** This doc originally suggested draw.io or Excalidraw;
we committed hand-built SVG instead. SVG opens and edits in any vector tool (not just
draw.io), diffs as text in `git diff` rather than as an opaque binary blob, and needs
no proprietary editor or account to view or modify — anyone picking this up later can
open it in a browser. `architecture.png` is the exported-at-readable-resolution PNG
committed alongside it, per the requirement above.
