# AGENTS.md — /infra (Lane C)

Root rules: [../AGENTS.md](../AGENTS.md). Protocol: [../docs/AI_AGENT_PROTOCOL.md](../docs/AI_AGENT_PROTOCOL.md).
Full brief: [../docs/lanes/LANE_C_INTEGRATIONS.md](../docs/lanes/LANE_C_INTEGRATIONS.md).

## You are in Lane C

You may edit `/infra`, `/integrations` and `/fixtures`.
**You may not edit** `/agent`, `/api`, `/web` or `/contracts`.

## What lives here

Deployment: DynamoDB, S3, Lambda, EventBridge, SES, IAM (CDK), plus the AgentCore Runtime
and Memory configuration.

## Non-negotiables

1. **Nothing here may be required for `make demo`.** Mock mode runs with zero AWS. If a
   judge needs to deploy anything to see the product work, we have failed a hard rule
   requirement.
2. **Least privilege on every IAM role.** Judges do read the IAM.
3. **No secrets in code or in CDK context.** Secrets Manager only.
4. **`DEPLOY.md` must be followable by a stranger** — a teammate who has never deployed it
   should be able to, from a cold start.

## AgentCore notes

The old `bedrock-agentcore-starter-toolkit` Python CLI is deprecated. Use the AgentCore
CLI: `npm install -g @aws/agentcore`, then `agentcore create` / `dev` / `deploy` /
`invoke`. Runtime requires `linux/arm64`, port 8080, and `/invocations` (POST) plus
`/ping` (GET).

Use the `aws-knowledge` MCP server for current AgentCore documentation rather than
training data — it is a fast-moving service.

## Timebox

AgentCore deployment is capped at **two days** (see `docs/ROADMAP.md`). It is optional per
the hackathon rules and must never block the vertical slice.

## Before you finish

Append a dated entry to `docs/status/PROGRESS_C.md`.
