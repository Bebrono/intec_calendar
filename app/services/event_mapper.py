from __future__ import annotations

import re
from typing import Any

from app.models import CalendarEvent


SYNC_ID_RE = re.compile(r"\[SYNC_ID:\s*([^\]\s]+)\]")
SOURCE_RE = re.compile(r"\[SOURCE:\s*([^\]\s]+)\]")


class EventMapper:
    def from_json(
        self,
        payload: dict[str, Any],
        *,
        source_system: str,
        source_owner: str,
    ) -> CalendarEvent:
        data = dict(payload)
        data["source_system"] = source_system
        data["source_owner"] = source_owner
        data.setdefault("status", "confirmed")
        data.setdefault("attendees", [])
        return CalendarEvent(**data)

    def to_json(self, event: CalendarEvent) -> dict[str, Any]:
        return {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "organizer": event.organizer,
            "attendees": list(event.attendees),
            "status": event.status,
            "updated_at": event.updated_at.isoformat(),
        }

    def extract_sync_id(self, description: str | None) -> str | None:
        if not description:
            return None
        match = SYNC_ID_RE.search(description)
        return match.group(1) if match else None

    def extract_source(self, description: str | None) -> str | None:
        if not description:
            return None
        match = SOURCE_RE.search(description)
        return match.group(1) if match else None

    def with_sync_metadata(
        self,
        description: str | None,
        *,
        sync_group_id: str,
        original_source_system: str,
    ) -> str:
        base_lines = []
        for line in (description or "").splitlines():
            stripped = line.strip()
            if SYNC_ID_RE.fullmatch(stripped) or SOURCE_RE.fullmatch(stripped):
                continue
            base_lines.append(line)

        base = "\n".join(base_lines).strip()
        metadata = f"[SYNC_ID: {sync_group_id}]\n[SOURCE: {original_source_system}]"
        return f"{base}\n\n{metadata}" if base else metadata

    def clone_for_calendar(
        self,
        event: CalendarEvent,
        *,
        event_id: str,
        source_system: str,
        source_owner: str,
        sync_group_id: str,
        original_source_system: str,
    ) -> CalendarEvent:
        return event.model_copy(
            update={
                "id": event_id,
                "source_system": source_system,
                "source_owner": source_owner,
                "description": self.with_sync_metadata(
                    event.description,
                    sync_group_id=sync_group_id,
                    original_source_system=original_source_system,
                ),
            }
        )

    def strip_sync_metadata(self, description: str | None) -> str:
        kept = []
        for line in (description or "").splitlines():
            stripped = line.strip()
            if SYNC_ID_RE.fullmatch(stripped) or SOURCE_RE.fullmatch(stripped):
                continue
            kept.append(line)
        return "\n".join(kept).strip()
