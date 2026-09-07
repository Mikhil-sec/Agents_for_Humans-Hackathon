"""Mock `CalendarProvider` — reads `fixtures/calendar.json`.

A flat list of events, documented in `fixtures/README.md`. Each entry's
`occurred_at` is its start time; `end_at` is optional and defaults to a
`DEFAULT_DURATION` slot when a fixture entry omits it.

`create_event` only appends to an in-memory list scoped to this provider
instance — one agent run, one bundle, one set of events created during it. It
never writes back to `calendar.json`, which is Lane C's committed fixture data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from quiet_hours_contracts import Signal, SignalKind

from ._fixtures import load_json, new_id, parse_dt, require_household, signal_from_raw

DEFAULT_SOURCE = "mock_calendar"
DEFAULT_DURATION = timedelta(minutes=30)


class MockCalendarProvider:
    """Satisfies `quiet_hours_integrations.base.CalendarProvider`."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir
        self.created_events: list[dict] = []
        """Every event created this session, for tests and for the digest."""

    def _event_window(self, raw: dict[str, Any]) -> tuple[datetime, datetime]:
        start = parse_dt(raw["occurred_at"])
        end = parse_dt(raw["end_at"]) if raw.get("end_at") else start + DEFAULT_DURATION
        return start, end

    def _events(self, household_id: str) -> list[tuple[Signal, datetime, datetime]]:
        require_household(self._fixtures_dir, household_id)
        raw_events: list[dict[str, Any]] = load_json(self._fixtures_dir / "calendar.json")
        events = []
        for raw in raw_events:
            signal = signal_from_raw(
                raw,
                household_id=household_id,
                kind=SignalKind.CALENDAR_EVENT,
                default_source=DEFAULT_SOURCE,
            )
            start, end = self._event_window(raw)
            events.append((signal, start, end))
        for created in self.created_events:
            if created["household_id"] != household_id:
                continue
            signal = Signal(
                signal_id=created["event_id"],
                household_id=household_id,
                kind=SignalKind.CALENDAR_EVENT,
                occurred_at=created["start"],
                ingested_at=created["start"],
                source=DEFAULT_SOURCE,
                subject=created["title"],
                body=created["notes"],
            )
            events.append((signal, created["start"], created["end"]))
        return events

    def fetch_between(self, household_id: str, start: datetime, end: datetime) -> list[Signal]:
        signals = [
            signal
            for signal, ev_start, ev_end in self._events(household_id)
            if ev_start < end and ev_end > start
        ]
        signals.sort(key=lambda s: s.occurred_at)
        return signals

    def find_free_slots(
        self, household_id: str, start: datetime, end: datetime, duration_minutes: int
    ) -> list[tuple[datetime, datetime]]:
        duration = timedelta(minutes=duration_minutes)
        busy = sorted(
            (ev_start, ev_end)
            for _, ev_start, ev_end in self._events(household_id)
            if ev_start < end and ev_end > start
        )

        free: list[tuple[datetime, datetime]] = []
        cursor = start
        for busy_start, busy_end in busy:
            busy_start = max(busy_start, start)
            if busy_start - cursor >= duration:
                free.append((cursor, busy_start))
            cursor = max(cursor, min(busy_end, end))
        if end - cursor >= duration:
            free.append((cursor, end))
        return free

    def create_event(
        self,
        household_id: str,
        title: str,
        start: datetime,
        end: datetime,
        notes: str | None = None,
    ) -> str:
        require_household(self._fixtures_dir, household_id)
        event_id = new_id("evt")
        self.created_events.append(
            {
                "event_id": event_id,
                "household_id": household_id,
                "title": title,
                "start": start,
                "end": end,
                "notes": notes,
            }
        )
        return event_id
