# Deployment runbook

**This must be followable by a stranger.** A teammate who has never deployed the
project should get from a cold start to a working stack using only this file.
Lane C owns it; test it by handing it to someone else before 11 September.

Nothing here is required for `make demo` — mock mode runs with zero AWS.

## Prerequisites

- AWS account with Bedrock model access enabled for Claude Sonnet 4.5
- AWS CLI configured
- Node 20+, Python 3.11+
- AgentCore CLI: `npm install -g @aws/agentcore`
  (the old `bedrock-agentcore-starter-toolkit` Python CLI is deprecated)

## Order

1. **Data layer** — `cd infra/cdk && npx cdk deploy QuietHoursData`
   DynamoDB table, S3 session bucket, IAM roles.
2. **Agent → AgentCore Runtime** — `agentcore create`, `agentcore deploy`
   Requires `linux/arm64`, port 8080, `/invocations` + `/ping`.
3. **AgentCore Memory** — create the memory store, record the id.
4. **API → Lambda** — `npx cdk deploy QuietHoursApi`
5. **Schedule** — `npx cdk deploy QuietHoursSchedule` (EventBridge cron, 07:00 local)
6. **SES** — verify the sender identity; request production access if needed.
7. **Web → Amplify** — connect the repo, set `NEXT_PUBLIC_API_URL`, deploy.

## Environment variables

See each lane's `.env.example`. Real values live in Secrets Manager, never in the
repo and never in CDK context.

## Cost

New AWS accounts get up to $200 in AgentCore free-tier credits. Runtime bills only
on active consumption. AgentCore Identity is free when routed through Runtime or
Gateway — route it that way. Set a billing alarm before the first deploy.

## Teardown

`npx cdk destroy --all`, then delete the AgentCore runtime and memory store, then
check for orphaned ECR images and CloudWatch log groups.
