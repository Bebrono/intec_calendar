from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.adapters.base import CalendarAdapter
from app.models import CalendarEvent
from app.services.google_event_mapper import GoogleEventMapper


class GoogleCalendarAdapter(CalendarAdapter):
    def __init__(
        self,
        *,
        service,
        owner: str = "developer_2",
        calendar_id: str = "primary",
        mapper: GoogleEventMapper | None = None,
    ) -> None:
        self.service = service
        self.owner = owner
        self.system = "google"
        self.calendar_id = calendar_id
        self.mapper = mapper or GoogleEventMapper()

    def get_events(self) -> list[CalendarEvent]:
        request = self.service.events().list(
            calendarId=self.calendar_id,
            maxResults=2500,
            singleEvents=True,
            showDeleted=True,
        )
        events = []
        while request is not None:
            response = request.execute()
            for item in response.get("items", []):
                if self._is_supported_event(item):
                    events.append(self.mapper.from_google(item, source_owner=self.owner))
            request = self.service.events().list_next(request, response)
        return events

    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        created = (
            self.service.events()
            .insert(calendarId=self.calendar_id, body=self.mapper.to_google(event))
            .execute()
        )
        return self.mapper.from_google(created, source_owner=self.owner)

    def update_event(self, event_id: str, event: CalendarEvent) -> CalendarEvent:
        updated = (
            self.service.events()
            .update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=self.mapper.to_google(event),
            )
            .execute()
        )
        return self.mapper.from_google(updated, source_owner=self.owner)

    def delete_event(self, event_id: str) -> CalendarEvent:
        current = (
            self.service.events()
            .get(calendarId=self.calendar_id, eventId=event_id)
            .execute()
        )
        deleted = self.mapper.from_google(current, source_owner=self.owner).model_copy(
            update={
                "status": "deleted",
                "updated_at": datetime.now(ZoneInfo(self.mapper.timezone)).replace(
                    microsecond=0,
                    tzinfo=None,
                ),
            }
        )
        self.service.events().delete(
            calendarId=self.calendar_id,
            eventId=event_id,
        ).execute()
        return deleted

    def _is_supported_event(self, payload: dict) -> bool:
        if payload.get("eventType") not in (None, "default"):
            return False
        return bool(payload.get("start") and payload.get("end"))
