"""AgentCore Runtime entrypoint.

Deployed to Amazon Bedrock AgentCore Runtime. Requirements the platform imposes:
`linux/arm64`, port 8080, `POST /invocations` and `GET /ping` — all provided by
`BedrockAgentCoreApp`.

LANE A: verify the current API before fleshing this out. The old
`bedrock-agentcore-starter-toolkit` CLI is deprecated; the current tool is the
AgentCore CLI (`npm install -g @aws/agentcore`, then `agentcore create` / `dev` /
`deploy` / `invoke`). Use the `aws-knowledge` MCP server for current docs.

Local test:
    python -m quiet_hours_agent.main
    curl -X POST http://localhost:8080/invocations \
      -H 'Content-Type: application/json' -d '{"household_id":"hh_demo"}'
"""

from __future__ import annotations

import os
from typing import Any

# from bedrock_agentcore.runtime import BedrockAgentCoreApp
# app = BedrockAgentCoreApp()


# @app.entrypoint
async def invoke(payload: dict[str, Any]):
    """One scheduled run, or a resume after the user answered a decision.

    Two entry paths:

      {"household_id": "..."}                      -> a fresh scheduled run
      {"decision_response": {...}, "session_id": "..."}  -> resume a suspended run

    The resume path rehydrates the Strands session from S3 and continues the tool
    call that was interrupted, which may have been days ago.

    TODO(Lane A):
        agent = build_agent(household_id, mode)
        async for event in agent.stream_async(prompt):
            yield event
    """
    raise NotImplementedError("Lane A: see docs/lanes/LANE_A_AGENT.md, build order A1-A7")


if __name__ == "__main__":
    os.environ.setdefault("QH_PROVIDER_MODE", "mock")
    # app.run()
    raise SystemExit("Lane A: uncomment BedrockAgentCoreApp once strands + bedrock-agentcore are installed")
