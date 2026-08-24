# Quiet Hours agent — Amazon Bedrock AgentCore Runtime container.
#
# AgentCore imposes four things on the image, and getting any of them wrong
# produces a deploy that fails its health check with no useful message:
#
#   1. linux/arm64  — AgentCore Runtime runs ARM only. An accidental amd64 build
#                     from an Intel laptop is the classic first failure.
#   2. port 8080    — where the platform sends traffic.
#   3. POST /invocations, GET /ping — both provided by BedrockAgentCoreApp.
#
# Build and push (Lane C owns the ECR repository and the runtime IAM role; this
# file only owns what goes *inside* the image):
#
#   docker buildx build --platform linux/arm64 -t quiet-hours-agent:latest agent
#
# The deploy itself is the AgentCore CLI — `npm install -g @aws/agentcore`, then
# `agentcore create` / `deploy` / `invoke`. The old
# `bedrock-agentcore-starter-toolkit` CLI is deprecated; do not follow a tutorial
# that uses it.

FROM --platform=linux/arm64 python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    QH_PROVIDER_MODE=live

WORKDIR /app

# Contracts first: they change least often, so this layer survives most rebuilds.
COPY contracts/python /app/contracts/python
RUN pip install --no-cache-dir /app/contracts/python

COPY integrations /app/integrations
RUN pip install --no-cache-dir /app/integrations

COPY agent /app/agent
RUN pip install --no-cache-dir /app/agent

# Non-root: the runtime does not require it, but nothing in this container needs
# to write outside its own tmpdir — sessions go to S3 and records to DynamoDB.
RUN useradd --create-home --uid 10001 quiethours
USER quiethours

EXPOSE 8080

# `GET /ping` is the platform's health check. A container that answers it while
# the agent itself is broken is worse than one that fails to start, so the check
# imports the entrypoint rather than merely opening the socket.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8080/ping', timeout=4)"

CMD ["python", "-m", "quiet_hours_agent.main"]
