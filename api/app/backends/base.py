"""The store seam.

Both backends return **contract models**, never dicts. Everything above this line
— the routers, the digest renderer — is written once against this Protocol and
does not know or care whether the data came from `/fixtures` or DynamoDB.

That is the whole point: `QH_BACKEND=fixtures` is not a stub of the API, it is a
stub of the *store*. Swapping it changes one factory call.
"""

from __future__ import annotations

from typing import Protocol

from quiet_hours_contracts import (
    ActivityEntry,
    DailyBrief,
    DecisionCard,
    DecisionResponse,
    Household,
    Policy,
    Run,
)


class Backend(Protocol):
    """Read and write access to one household's Quiet Hours state."""

    name: str

    def household(self) -> Household: ...

    def list_decisions(self, *, status: str | None = None) -> list[DecisionCard]: ...

    def get_decision(self, decision_id: str) -> DecisionCard | None: ...

    def respond(self, card: DecisionCard, response: DecisionResponse) -> tuple[str, str]:
        """Persist the answer and resume the suspended run.

        Returns `(run_id, run_status)`. The `interrupt_id` on the card is handed
        back to the agent verbatim — never parsed, never reconstructed.
        """
        ...

    def list_runs(self) -> list[Run]: ...

    def get_run(self, run_id: str) -> Run | None: ...

    def trigger_run(self) -> Run: ...

    def list_activity(self, *, autonomous: bool | None = None) -> list[ActivityEntry]: ...

    def list_policies(self, *, include_revoked: bool = False) -> list[Policy]: ...

    def get_policy(self, policy_id: str) -> Policy | None: ...

    def revoke_policy(self, policy_id: str) -> Policy | None: ...

    def latest_brief(self) -> DailyBrief | None: ...
