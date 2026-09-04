"""The live backend — DynamoDB, plus a real resume of the suspended Strands run.

The table layout is Lane A's, recorded in `docs/status/DECISIONS.md` (2026-08-24,
"DynamoDB single-table layout"):

| Attribute | Example | Purpose |
|---|---|---|
| `pk` / `sk` | `DECISION#dec_abc` | the record's own id, both the same |
| `gsi1pk`    | `HH#hh_demo#DECISION` | one household's records of one type |
| `gsi1sk`    | `2026-08-24T07:15:00Z` | timestamp, so lists come back ordered |
| `type`      | `DECISION` | `ACTION` / `DECISION` / `ACTIVITY` / `POLICY` / `RUN` |
| `body`      | `{"decision_id": ...}` | the contract model as JSON text |

**Why this file does not import Lane A's `store.py`.** It would work, and it would
also mean the API could not deploy without the agent package and its Strands
dependency tree on the Lambda. The layout above is a written cross-lane contract,
so both lanes implement it against the document rather than against each other's
code. `body` is the frozen contract model as JSON either way, and both sides parse
it with the same pydantic models — which is the part that actually has to agree.

**Resume.** `POST /api/decisions/{id}/respond` persists the answer and then wakes
the run: AgentCore Runtime when `QH_AGENT_RUNTIME_ARN` is set, otherwise plain
HTTP to `QH_AGENT_URL` (what `make agent-serve` exposes). The payload shape is
Lane A's, from `docs/status/PROGRESS_A.md`:

    {"household_id": "...", "decision_response": {...}}

`session_id`, `interrupt_id` and `interrupt_name` are **opaque**. They travel on
the card, get echoed back untouched, and are never parsed or constructed here.

**Status: written, not yet exercised against real AWS.** No AgentCore deploy has
happened (Lane A's note, and `/infra` is Lane C). Every screen in the web app is
built and demoed against `QH_BACKEND=fixtures`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel
from quiet_hours_contracts import (
    ActivityEntry,
    DailyBrief,
    DecisionCard,
    DecisionResponse,
    DecisionStatus,
    Household,
    Policy,
    Run,
    RunStatus,
    RunTrigger,
)

from ..config import (
    AGENT_RUNTIME_ARN,
    AGENT_URL,
    AWS_REGION,
    DEFAULT_HOUSEHOLD_ID,
    TABLE_NAME,
)
from ..errors import AGENT_UNAVAILABLE, BACKEND_ERROR, ApiProblem

M = TypeVar("M", bound=BaseModel)

DECISION = "DECISION"
ACTIVITY = "ACTIVITY"
POLICY = "POLICY"
RUN = "RUN"


def _now() -> datetime:
    return datetime.now(UTC)


class DynamoBackend:
    """Reads and writes the single table. One household per deployment."""

    name = "live"

    def __init__(self, table: Any | None = None, household_id: str | None = None) -> None:
        self.household_id = household_id or DEFAULT_HOUSEHOLD_ID
        if table is not None:
            self._table = table
            return
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - boto3 is a declared dep
            raise ApiProblem(BACKEND_ERROR, "QH_BACKEND=live needs boto3 installed", 500) from exc
        self._table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)

    # -- table primitives ---------------------------------------------------

    @staticmethod
    def _key(record_type: str, record_id: str) -> str:
        return f"{record_type}#{record_id}"

    def _household_key(self, record_type: str) -> str:
        return f"HH#{self.household_id}#{record_type}"

    def _get(self, record_type: str, record_id: str, model: type[M]) -> M | None:
        key = self._key(record_type, record_id)
        item = self._table.get_item(Key={"pk": key, "sk": key}).get("Item")
        if not item:
            return None
        return model.model_validate_json(item["body"])

    def _query(self, record_type: str, model: type[M]) -> list[M]:
        """Every record of one type for this household, newest first.

        No pagination — deliberate, and recorded as such in `DECISIONS.md`. One
        demo household does not fill a 1 MB page; a year of activity would, and
        this is where that gets fixed.
        """
        result = self._table.query(
            IndexName="gsi1",
            KeyConditionExpression="gsi1pk = :pk",
            ExpressionAttributeValues={":pk": self._household_key(record_type)},
            ScanIndexForward=False,
        )
        return [model.model_validate_json(item["body"]) for item in result.get("Items", [])]

    def _put(self, record_type: str, record_id: str, when: datetime, model: BaseModel) -> None:
        key = self._key(record_type, record_id)
        self._table.put_item(
            Item={
                "pk": key,
                "sk": key,
                "gsi1pk": self._household_key(record_type),
                "gsi1sk": when.isoformat().replace("+00:00", "Z"),
                "type": record_type,
                "body": model.model_dump_json(),
            }
        )

    # -- household ----------------------------------------------------------

    def household(self) -> Household:
        """There is no HOUSEHOLD record type in the layout, so this is assembled
        from configuration. The agent reads the same environment."""
        return Household(
            household_id=self.household_id,
            display_name=self.household_id,
            created_at=_now(),
        )

    # -- decisions ----------------------------------------------------------

    def list_decisions(self, *, status: str | None = None) -> list[DecisionCard]:
        cards = self._query(DECISION, DecisionCard)
        if status:
            cards = [c for c in cards if c.status.value == status]
        return cards

    def get_decision(self, decision_id: str) -> DecisionCard | None:
        return self._get(DECISION, decision_id, DecisionCard)

    def respond(self, card: DecisionCard, response: DecisionResponse) -> tuple[str, str]:
        """Persist the answer, then hand the interrupt back to the agent.

        Persist first: if the resume call fails, the user's answer is still
        recorded and the run can be resumed again. Losing an answer the user
        already gave is the worse of the two failures.
        """
        resolved = card.model_copy(
            update={
                "status": DecisionStatus.RESOLVED,
                "resolved_at": response.responded_at,
            }
        )
        self._put(DECISION, card.decision_id, resolved.created_at, resolved)
        self._resume(response)
        run = self.get_run(card.run_id)
        return card.run_id, (run.status.value if run else RunStatus.RUNNING.value)

    def _resume(self, response: DecisionResponse) -> None:
        """Wake the suspended run. The card carries its own session id, so none
        is passed here — see `docs/status/PROGRESS_A.md`."""
        payload = {
            "household_id": self.household_id,
            "decision_response": response.model_dump(mode="json"),
        }
        if AGENT_RUNTIME_ARN:
            self._invoke_agentcore(payload)
        elif AGENT_URL:
            self._invoke_http(payload)
        else:
            raise ApiProblem(
                AGENT_UNAVAILABLE,
                "QH_BACKEND=live needs QH_AGENT_RUNTIME_ARN or QH_AGENT_URL to resume a run",
                503,
            )

    def _invoke_agentcore(self, payload: dict[str, Any]) -> None:
        try:
            import boto3

            client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
            client.invoke_agent_runtime(
                agentRuntimeArn=AGENT_RUNTIME_ARN,
                payload=json.dumps(payload).encode("utf-8"),
            )
        except Exception as exc:
            raise ApiProblem(AGENT_UNAVAILABLE, f"could not resume the run: {exc}", 503) from exc

    def _invoke_http(self, payload: dict[str, Any]) -> None:
        try:
            import httpx

            httpx.post(f"{AGENT_URL.rstrip('/')}/invocations", json=payload, timeout=30.0)
        except Exception as exc:
            raise ApiProblem(AGENT_UNAVAILABLE, f"could not resume the run: {exc}", 503) from exc

    # -- runs ---------------------------------------------------------------

    def list_runs(self) -> list[Run]:
        return self._query(RUN, Run)

    def get_run(self, run_id: str) -> Run | None:
        return self._get(RUN, run_id, Run)

    def trigger_run(self) -> Run:
        """The demo button. Asks the agent for a fresh run and records it as
        `running`; the agent owns it from here and writes its own updates."""
        run = Run(
            run_id=f"run_{_now().strftime('%Y%m%d%H%M%S')}",
            household_id=self.household_id,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.RUNNING,
            session_id="",
            started_at=_now(),
        )
        payload = {"household_id": self.household_id}
        if AGENT_RUNTIME_ARN:
            self._invoke_agentcore(payload)
        elif AGENT_URL:
            self._invoke_http(payload)
        else:
            raise ApiProblem(
                AGENT_UNAVAILABLE,
                "QH_BACKEND=live needs QH_AGENT_RUNTIME_ARN or QH_AGENT_URL to start a run",
                503,
            )
        return run

    # -- activity -----------------------------------------------------------

    def list_activity(self, *, autonomous: bool | None = None) -> list[ActivityEntry]:
        entries = self._query(ACTIVITY, ActivityEntry)
        if autonomous is not None:
            entries = [e for e in entries if e.was_autonomous is autonomous]
        return entries

    # -- policies -----------------------------------------------------------

    def list_policies(self, *, include_revoked: bool = False) -> list[Policy]:
        policies = self._query(POLICY, Policy)
        if not include_revoked:
            policies = [p for p in policies if p.is_active]
        return policies

    def get_policy(self, policy_id: str) -> Policy | None:
        return self._get(POLICY, policy_id, Policy)

    def revoke_policy(self, policy_id: str) -> Policy | None:
        policy = self.get_policy(policy_id)
        if policy is None:
            return None
        if policy.revoked_at is not None:
            return policy
        revoked = policy.model_copy(update={"revoked_at": _now()})
        self._put(POLICY, policy_id, revoked.created_at, revoked)
        return revoked

    # -- brief --------------------------------------------------------------

    def latest_brief(self) -> DailyBrief | None:
        """There is no BRIEF record type in the layout, so the brief is derived
        from the newest run plus current state — the same fields the agent would
        have written."""
        runs = self.list_runs()
        if not runs:
            return None
        run = runs[0]
        pending = [c.decision_id for c in self.list_decisions(status="pending")]
        silent = [e.summary for e in self.list_activity(autonomous=True)]
        total = len(self.list_activity())
        headline = "Nothing needs you today"
        if len(pending) == 1:
            headline = "One thing needs you today"
        elif pending:
            headline = f"{len(pending)} things need you today"
        return DailyBrief(
            brief_id=f"brf_{run.run_id}",
            household_id=self.household_id,
            run_id=run.run_id,
            generated_at=run.finished_at or run.started_at,
            headline=headline,
            handled_silently=silent[:12],
            pending_decision_ids=pending,
            savings_this_month=run.stats.estimated_annual_savings,
            autonomy_rate=(len(silent) / total) if total else 1.0,
        )
