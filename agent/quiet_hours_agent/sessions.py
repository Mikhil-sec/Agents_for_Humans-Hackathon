"""Where a suspended run's state lives between processes.

A Quiet Hours run can stop mid-tool-call and stay stopped for days, because the
thing it is waiting for is a human. Everything needed to pick that tool call back
up — the node's messages and the pending interrupt, including its
`tool_use_message` — is written by a Strands `SessionManager`. Choosing the wrong
one is how a decision card becomes unanswerable.

    mock  ->  FileSessionManager, under `.local/sessions`
    live  ->  S3SessionManager

Live mode has to be S3. On AgentCore Runtime the container that suspends a run
and the container that resumes it two days later are not the same machine and
share no disk; a `FileSessionManager` there writes state that the resume can
never find. The run would look resumable — the card is in DynamoDB, the API
accepts the answer — and then fail with `no interrupt found`, which is the worst
kind of failure because it only shows up in production.

**The A5 constraint applies to everything this module returns:** it is handed to
`GraphBuilder.set_session_manager()`, never to a node `Agent`. Strands raises
`ValueError("Session persistence is not supported for Graph agents yet.")` if a
node executor carries its own. See `graph.py`, note 2.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_S3_PREFIX = "sessions/"

SESSION_BUCKET_ENV = "QH_SESSION_BUCKET"
SESSION_PREFIX_ENV = "QH_SESSION_PREFIX"


class SessionConfigError(RuntimeError):
    """Live mode was asked for without the configuration it requires."""


def session_id_for(household_id: str, run_id: str | None = None) -> str:
    """The session id for one run.

    **One session per run, not per household.** A household-wide id looks tidier
    and is wrong twice over. Strands rehydrates a session's messages, so today's
    ingest node would wake up holding last Tuesday's conversation — and once a
    run has been resumed its session still carries a spent interrupt state, so
    the *next* scheduled run starts by trying to resume it and dies with
    `must resume from interrupt with list of interruptResponse's`. Both faults
    are invisible until a second run happens, which is never during development.

    The resume path never has to derive this: `DecisionCard.session_id` carries
    it, written when the card was raised. That is what makes it safe for the id
    to be per-run rather than guessable.

    Omitting `run_id` gives the household-wide form `local_run.py` uses, which
    manages the same problem by deleting the session directory before each run —
    an option the deployed path does not have, because there the sessions live in
    S3 and the container doing the deleting is not the one that wrote them.
    """
    return f"qh-{household_id}-{run_id}" if run_id else f"qh-{household_id}"


def build_session_manager(
    session_id: str,
    *,
    mode: str | None = None,
    session_dir: Path | str | None = None,
) -> Any:
    """The session manager for this run.

    Args:
        session_id: Must be identical when starting and when resuming. A resume
            with a different id rehydrates nothing and raises `no interrupt found`.
        mode: `live` or `mock`. Defaults to `QH_PROVIDER_MODE`, then `mock`.
        session_dir: Where mock mode writes. Ignored in live mode.

    Raises:
        SessionConfigError: live mode with no `QH_SESSION_BUCKET`. Deliberately
            loud. Falling back to local files here would produce a system that
            passes every smoke test and silently loses every suspended run.
    """
    resolved = (mode or os.environ.get("QH_PROVIDER_MODE") or "mock").strip().casefold()

    if resolved == "live":
        return _s3_session_manager(session_id)

    from strands.session import FileSessionManager

    directory = Path(session_dir or os.environ.get("QH_SESSION_DIR") or ".local/sessions")
    directory.mkdir(parents=True, exist_ok=True)
    return FileSessionManager(session_id=session_id, storage_dir=str(directory))


def _s3_session_manager(session_id: str) -> Any:
    from strands.session import S3SessionManager

    bucket = os.environ.get(SESSION_BUCKET_ENV, "").strip()
    if not bucket:
        raise SessionConfigError(
            f"live mode needs {SESSION_BUCKET_ENV} — the bucket Strands sessions are "
            "written to. Without it a suspended run cannot be resumed by another "
            "container. Set QH_PROVIDER_MODE=mock to run offline."
        )

    logger.info("session %s -> s3://%s", session_id, bucket)
    return S3SessionManager(
        session_id=session_id,
        bucket=bucket,
        prefix=os.environ.get(SESSION_PREFIX_ENV, DEFAULT_S3_PREFIX),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
