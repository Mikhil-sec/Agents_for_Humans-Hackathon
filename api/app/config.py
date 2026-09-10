"""Runtime configuration for the Quiet Hours API.

One knob matters: `QH_BACKEND`.

    QH_BACKEND=fixtures   static contract-shaped JSON from /fixtures  (default)
    QH_BACKEND=live       DynamoDB, and resumes real Strands sessions

`fixtures` must always work with zero credentials — it is how Lane B builds every
screen without the agent, and it is what `make demo` serves to a judge.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(os.environ.get("QH_FIXTURES_DIR", REPO_ROOT / "fixtures"))

BACKEND = os.environ.get("QH_BACKEND", "fixtures").strip().lower()

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("QH_CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

DEFAULT_HOUSEHOLD_ID = os.environ.get("QH_HOUSEHOLD_ID", "hh_demo")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# --- live backend only -----------------------------------------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
TABLE_NAME = os.environ.get("QH_TABLE_NAME", "quiet-hours")
AGENT_RUNTIME_ARN = os.environ.get("QH_AGENT_RUNTIME_ARN", "")
AGENT_URL = os.environ.get("QH_AGENT_URL", "")
"""HTTP endpoint of `make agent-serve`, used to resume a run when no AgentCore
runtime ARN is configured."""
