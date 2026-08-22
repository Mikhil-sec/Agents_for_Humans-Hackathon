# Assets

| File | Owner | Status |
|---|---|---|
| `architecture.png` | Lane C | **Required deliverable** — not yet created |
| `architecture.drawio` | Lane C | Source file, commit alongside the export |
| `screenshot-today.png` | Lane B | For the README |
| `screenshot-insights.png` | Lane B | The autonomy chart |

## The architecture diagram

A hard submission requirement. It must clearly label:

- **User input / interface** — the web app and the digest email
- **Strands Agents** — the core agent and its loop (model → tools → reasoning → response)
- **Tools & integrations** — email, transactions, calendar, DuckDuckGo MCP, Playwright MCP
- **AWS services** — Bedrock, AgentCore Runtime + Memory, Lambda, DynamoDB, S3, EventBridge, SES, Amplify
- **Output** — decision cards, the activity trail, the digest

`docs/ARCHITECTURE.md` has an ASCII version to work from. Use draw.io or Excalidraw
with official AWS icons, export a PNG at a readable resolution, and commit the
source file too so it can be edited later.
