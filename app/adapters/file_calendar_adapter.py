from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.adapters.base import CalendarAdapter
from app.models import CalendarEvent
from app.services.event_mapper import EventMapper


class FileCalendarAdapter(CalendarAdapter):
    def __init__(
        self,
        *,
        file_path: Path,
        owner: str,
        system: str,
        mapper: EventMapper | None = None,
    ) -> None:
        self.file_path = file_path
        self.owner = owner
        self.system = system
        self.mapper = mapper or EventMapper()

    def get_events(self) -> list[CalendarEvent]:
        return [
            self.mapper.from_json(
                item,
                source_system=self.system,
                source_owner=self.owner,
            )
            for item in self._read_raw_events()
        ]

    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        raw_events = self._read_raw_events()
        event_id = event.id or self._generate_event_id()
        if any(item.get("id") == event_id for item in raw_events):
            event_id = self._generate_event_id()

        calendar_event = event.with_calendar_identity(
            event_id=event_id,
            source_system=self.system,
            source_owner=self.owner,
        )
        raw_events.append(self.mapper.to_json(calendar_event))
        self._write_raw_events(raw_events)
        return calendar_event

    def update_event(self, event_id: str, event: CalendarEvent) -> CalendarEvent:
        raw_events = self._read_raw_events()
        calendar_event = event.with_calendar_identity(
            event_id=event_id,
            source_system=self.system,
            source_owner=self.owner,
        )
        for index, item in enumerate(raw_events):
            if item.get("id") == event_id:
                raw_events[index] = self.mapper.to_json(calendar_event)
                self._write_raw_events(raw_events)
                return calendar_event
        raise KeyError(f"Event {event_id!r} not found in {self.file_path}")

    def delete_event(self, event_id: str) -> CalendarEvent:
        raw_events = self._read_raw_events()
        for index, item in enumerate(raw_events):
            if item.get("id") == event_id:
                item["status"] = "deleted"
                item["updated_at"] = datetime.now().replace(microsecond=0).isoformat()
                raw_events[index] = item
                self._write_raw_events(raw_events)
                return self.mapper.from_json(
                    item,
                    source_system=self.system,
                    source_owner=self.owner,
                )
        raise KeyError(f"Event {event_id!r} not found in {self.file_path}")

    def _generate_event_id(self) -> str:
        return f"{self.system}_{self.owner}_{uuid4().hex[:12]}"

    def _read_raw_events(self) -> list[dict]:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON calendar file: {self.file_path}") from exc

        if not isinstance(data, list):
            raise ValueError(f"Calendar file must contain a JSON array: {self.file_path}")
        return data

    def _write_raw_events(self, events: list[dict]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps(events, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
