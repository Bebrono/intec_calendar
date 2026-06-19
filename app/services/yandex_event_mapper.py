from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from app.models import CalendarEvent
from app.services.google_event_mapper import DEFAULT_TIMEZONE


SYNC_UPDATED_AT_KEY = "X-CALENDAR-SYNC-UPDATED-AT"
SYNC_ORGANIZER_KEY = "X-CALENDAR-SYNC-ORGANIZER"
SYNC_ATTENDEES_KEY = "X-CALENDAR-SYNC-ATTENDEES"
SYNC_STATUS_KEY = "X-CALENDAR-SYNC-STATUS"
DESCRIPTION_STATUS_RE = re.compile(r"\[SYNC_STATUS:\s*([^\]\s]+)\]")
DESCRIPTION_UPDATED_AT_RE = re.compile(r"\[SYNC_UPDATED_AT:\s*([^\]]+)\]")


class YandexEventMapper:
    def __init__(self, *, timezone: str = DEFAULT_TIMEZONE) -> None:
        self.timezone = timezone

    def from_ical(
        self,
        payload: str | bytes,
        *,
        source_owner: str,
    ) -> CalendarEvent:
        calendar = Calendar.from_ical(payload)
        vevent = self._first_event(calendar)
        raw_description = self._optional_text(vevent.get("DESCRIPTION"))
        status = self._extract_status(vevent, raw_description)
        if status == "cancelled":
            status = "deleted"

        return CalendarEvent(
            id=str(vevent.get("UID")),
            title=str(vevent.get("SUMMARY", "(no title)")),
            description=self._strip_description_metadata(raw_description),
            start_time=self._to_local_naive(vevent.decoded("DTSTART")),
            end_time=self._to_local_naive(vevent.decoded("DTEND")),
            organizer=self._extract_organizer(vevent, source_owner),
            attendees=self._extract_attendees(vevent),
            source_system="yandex",
            source_owner=source_owner,
            status=status,
            updated_at=self._extract_updated_at(vevent),
        )

    def to_ical(self, event: CalendarEvent) -> str:
        calendar = Calendar()
        calendar.add("prodid", "-//Calendar Sync Service//EN")
        calendar.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", event.id)
        vevent.add("summary", event.title)
        vevent.add("description", self._with_description_metadata(event))
        vevent.add("dtstart", self._to_aware(event.start_time))
        vevent.add("dtend", self._to_aware(event.end_time))
        vevent.add("dtstamp", datetime.now(UTC))
        vevent.add("last-modified", self._to_utc(event.updated_at))
        vevent.add("status", "CANCELLED" if event.status == "deleted" else "CONFIRMED")
        vevent.add(SYNC_STATUS_KEY, event.status)
        vevent.add(SYNC_UPDATED_AT_KEY, event.updated_at.isoformat())
        vevent.add(SYNC_ORGANIZER_KEY, event.organizer)
        vevent.add(SYNC_ATTENDEES_KEY, json.dumps(event.attendees, ensure_ascii=False))
        calendar.add_component(vevent)
        return calendar.to_ical().decode("utf-8")

    def _first_event(self, calendar: Calendar) -> Event:
        for component in calendar.walk("VEVENT"):
            return component
        raise ValueError("iCalendar payload does not contain VEVENT")

    def _optional_text(self, value: Any) -> str | None:
        return str(value) if value is not None else None

    def _extract_organizer(self, vevent: Event, source_owner: str) -> str:
        if vevent.get(SYNC_ORGANIZER_KEY):
            return str(vevent.get(SYNC_ORGANIZER_KEY))
        organizer = vevent.get("ORGANIZER")
        if organizer:
            value = str(organizer)
            return value.removeprefix("mailto:")
        return source_owner

    def _extract_attendees(self, vevent: Event) -> list[str]:
        if vevent.get(SYNC_ATTENDEES_KEY):
            try:
                value = json.loads(str(vevent.get(SYNC_ATTENDEES_KEY)))
                if isinstance(value, list):
                    return [str(item) for item in value]
            except json.JSONDecodeError:
                return []

        attendees = vevent.get("ATTENDEE")
        if attendees is None:
            return []
        if not isinstance(attendees, list):
            attendees = [attendees]
        return [str(attendee).removeprefix("mailto:") for attendee in attendees]

    def _extract_status(self, vevent: Event, description: str | None) -> str:
        raw_status = str(vevent.get("STATUS", "")).lower()
        if raw_status == "cancelled":
            return raw_status
        if description:
            match = DESCRIPTION_STATUS_RE.search(description)
            if match:
                return match.group(1).lower()
        return str(vevent.get(SYNC_STATUS_KEY) or vevent.get("STATUS", "CONFIRMED")).lower()

    def _extract_updated_at(self, vevent: Event) -> datetime:
        if vevent.get("LAST-MODIFIED"):
            return self._to_local_naive(vevent.decoded("LAST-MODIFIED"))
        description = self._optional_text(vevent.get("DESCRIPTION"))
        if description:
            match = DESCRIPTION_UPDATED_AT_RE.search(description)
            if match:
                return datetime.fromisoformat(match.group(1).strip())
        if vevent.get(SYNC_UPDATED_AT_KEY):
            return datetime.fromisoformat(str(vevent.get(SYNC_UPDATED_AT_KEY)))
        if vevent.get("LAST-MODIFIED"):
            return self._to_local_naive(vevent.decoded("LAST-MODIFIED"))
        return datetime.now(ZoneInfo(self.timezone)).replace(microsecond=0, tzinfo=None)

    def _to_aware(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=ZoneInfo(self.timezone))

    def _to_utc(self, value: datetime) -> datetime:
        return self._to_aware(value).astimezone(UTC)

    def _to_local_naive(self, value: date | datetime) -> datetime:
        if isinstance(value, datetime):
            result = value
        else:
            result = datetime.combine(value, time.min)
        if result.tzinfo is not None:
            result = result.astimezone(ZoneInfo(self.timezone))
        return result.replace(tzinfo=None)

    def _with_description_metadata(self, event: CalendarEvent) -> str:
        base = self._strip_description_metadata(event.description) or ""
        metadata = (
            f"[SYNC_STATUS: {event.status}]\n"
            f"[SYNC_UPDATED_AT: {event.updated_at.isoformat()}]"
        )
        return f"{base}\n\n{metadata}" if base else metadata

    def _strip_description_metadata(self, description: str | None) -> str | None:
        if not description:
            return None
        kept = []
        for line in description.splitlines():
            stripped = line.strip()
            if DESCRIPTION_STATUS_RE.fullmatch(stripped):
                continue
            if DESCRIPTION_UPDATED_AT_RE.fullmatch(stripped):
                continue
            kept.append(line)
        result = "\n".join(kept).strip()
        return result or None
