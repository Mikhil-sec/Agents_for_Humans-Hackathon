"""Mock `EmailProvider` — reads `fixtures/inbox/*.json`.

One file per message, documented in `fixtures/README.md`. `create_draft` only
ever appends to an in-memory list and returns an id — there is no send path, in
mock mode or any other, matching the safety guarantee in `base.py`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from quiet_hours_contracts import Signal, SignalKind

from ._fixtures import load_json_dir, new_id, require_household, signal_from_raw

DEFAULT_SOURCE = "mock_gmail"


class MockEmailProvider:
    """Satisfies `quiet_hours_integrations.base.EmailProvider`."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir
        self.drafts: list[dict] = []
        """Every draft created this session, for tests and for the digest."""

    def _inbox(self, household_id: str) -> list[Signal]:
        require_household(self._fixtures_dir, household_id)
        raw_messages = load_json_dir(self._fixtures_dir / "inbox")
        return [
            signal_from_raw(
                raw,
                household_id=household_id,
                kind=SignalKind.EMAIL,
                default_source=DEFAULT_SOURCE,
            )
            for raw in raw_messages
        ]

    def fetch_since(self, household_id: str, since: datetime, limit: int = 200) -> list[Signal]:
        signals = [s for s in self._inbox(household_id) if s.occurred_at > since]
        signals.sort(key=lambda s: s.occurred_at)
        return signals[:limit]

    def create_draft(
        self,
        household_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> str:
        require_household(self._fixtures_dir, household_id)
        draft_id = new_id("draft")
        self.drafts.append(
            {
                "draft_id": draft_id,
                "household_id": household_id,
                "to": to,
                "subject": subject,
                "body": body,
                "in_reply_to": in_reply_to,
            }
        )
        return draft_id

    def get_thread(self, household_id: str, thread_ref: str) -> list[Signal]:
        require_household(self._fixtures_dir, household_id)
        raw_messages = load_json_dir(self._fixtures_dir / "inbox")
        thread = [
            signal_from_raw(
                raw,
                household_id=household_id,
                kind=SignalKind.EMAIL,
                default_source=DEFAULT_SOURCE,
            )
            for raw in raw_messages
            if raw.get("thread_id", raw.get("signal_id")) == thread_ref
        ]
        thread.sort(key=lambda s: s.occurred_at)
        return thread
