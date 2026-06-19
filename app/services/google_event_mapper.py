from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.models import CalendarEvent


DEFAULT_TIMEZONE = "Asia/Yekaterinburg"
SYNC_UPDATED_AT_KEY = "calendar_sync_updated_at"
SYNC_ORGANIZER_KEY = "calendar_sync_organizer"
SYNC_ATTENDEES_KEY = "calendar_sync_attendees"
SYNC_STATUS_KEY = "calendar_sync_status"


class GoogleEventMapper:
    def __init__(self, *, timezone: str = DEFAULT_TIMEZONE) -> None:
        self.timezone = timezone

    def from_google(
        self,
        payload: dict[str, Any],
        *,
        source_owner: str,
    ) -> CalendarEvent:
        start_time = self._parse_google_datetime(payload.get("start", {}))
        end_time = self._parse_google_datetime(payload.get("end", {}))
        private_properties = payload.get("extendedProperties", {}).get("private", {})
        payload_status = payload.get("status")
        updated_raw = payload.get("updated") or private_properties.get(
            SYNC_UPDATED_AT_KEY
        )
        updated_at = (
            self._parse_datetime(updated_raw)
            if updated_raw
            else datetime.now(ZoneInfo(self.timezone)).replace(microsecond=0)
        )
        status = (
            payload_status
            if payload_status == "cancelled"
            else private_properties.get(SYNC_STATUS_KEY) or payload_status or "confirmed"
        )
        if status == "cancelled":
            status = "deleted"

        return CalendarEvent(
            id=payload["id"],
            title=payload.get("summary") or "(no title)",
            description=payload.get("description"),
            start_time=start_time,
            end_time=end_time,
            organizer=self._extract_organizer(
                payload,
                private_properties,
                source_owner,
            ),
            attendees=self._extract_attendees(payload, private_properties),
            source_system="google",
            source_owner=source_owner,
            status=status,
            updated_at=updated_at,
        )

    def to_google(self, event: CalendarEvent) -> dict[str, Any]:
        status = "cancelled" if event.status == "deleted" else event.status
        body: dict[str, Any] = {
            "summary": event.title,
            "description": event.description or "",
            "start": {
                "dateTime": self._format_google_datetime(event.start_time),
                "timeZone": self.timezone,
            },
            "end": {
                "dateTime": self._format_google_datetime(event.end_time),
                "timeZone": self.timezone,
            },
            "status": status,
            "extendedProperties": {
                "private": {
                    SYNC_UPDATED_AT_KEY: event.updated_at.isoformat(),
                    SYNC_ORGANIZER_KEY: event.organizer,
                    SYNC_ATTENDEES_KEY: json.dumps(
                        event.attendees,
                        ensure_ascii=False,
                    ),
                    SYNC_STATUS_KEY: event.status,
                }
            },
        }
        email_attendees = [attendee for attendee in event.attendees if "@" in attendee]
        if email_attendees:
            body["attendees"] = [{"email": attendee} for attendee in email_attendees]
        return body

    def _parse_google_datetime(self, payload: dict[str, Any]) -> datetime:
        value = payload.get("dateTime") or payload.get("date")
        if not value:
            raise ValueError("Google event does not contain dateTime or date")
        return self._parse_datetime(value)

    def _parse_datetime(self, value: str) -> datetime:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        timezone = ZoneInfo(self.timezone)
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(timezone).replace(tzinfo=None)

    def _format_google_datetime(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(self.timezone))
        return value.isoformat()

    def _extract_organizer(
        self,
        payload: dict[str, Any],
        private_properties: dict[str, Any],
        source_owner: str,
    ) -> str:
        return (
            private_properties.get(SYNC_ORGANIZER_KEY)
            or payload.get("organizer", {}).get("email")
            or payload.get("creator", {}).get("email")
            or source_owner
        )

    def _extract_attendees(
        self,
        payload: dict[str, Any],
        private_properties: dict[str, Any],
    ) -> list[str]:
        private_attendees = private_properties.get(SYNC_ATTENDEES_KEY)
        if private_attendees:
            try:
                parsed = json.loads(private_attendees)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item) for item in parsed]

        return [
            attendee["email"]
            for attendee in payload.get("attendees", [])
            if attendee.get("email")
        ]
