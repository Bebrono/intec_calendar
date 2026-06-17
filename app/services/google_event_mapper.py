from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.models import CalendarEvent


DEFAULT_TIMEZONE = "Asia/Yekaterinburg"


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
        updated_raw = payload.get("updated")
        updated_at = (
            self._parse_datetime(updated_raw)
            if updated_raw
            else datetime.now(ZoneInfo(self.timezone)).replace(microsecond=0)
        )
        status = payload.get("status") or "confirmed"
        if status == "cancelled":
            status = "deleted"

        return CalendarEvent(
            id=payload["id"],
            title=payload.get("summary") or "(no title)",
            description=payload.get("description"),
            start_time=start_time,
            end_time=end_time,
            organizer=(
                payload.get("organizer", {}).get("email")
                or payload.get("creator", {}).get("email")
                or source_owner
            ),
            attendees=[
                attendee["email"]
                for attendee in payload.get("attendees", [])
                if attendee.get("email")
            ],
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
        return datetime.fromisoformat(normalized)

    def _format_google_datetime(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(self.timezone))
        return value.isoformat()
