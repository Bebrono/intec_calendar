from __future__ import annotations

from uuid import uuid4

from caldav import Calendar

from app.adapters.base import CalendarAdapter
from app.models import CalendarEvent
from app.services.yandex_event_mapper import YandexEventMapper


class YandexCalendarAdapter(CalendarAdapter):
    def __init__(
        self,
        *,
        calendar: Calendar,
        owner: str = "developer_1",
        mapper: YandexEventMapper | None = None,
    ) -> None:
        self.calendar = calendar
        self.owner = owner
        self.system = "yandex"
        self.mapper = mapper or YandexEventMapper()

    def get_events(self) -> list[CalendarEvent]:
        events = []
        for item in self.calendar.events():
            if getattr(item, "data", None):
                events.append(
                    self.mapper.from_ical(item.data, source_owner=self.owner)
                )
        return events

    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        event_id = event.id or self._generate_event_id()
        calendar_event = event.with_calendar_identity(
            event_id=event_id,
            source_system=self.system,
            source_owner=self.owner,
        )
        self.calendar.save_event(self.mapper.to_ical(calendar_event), no_overwrite=True)
        return calendar_event

    def update_event(self, event_id: str, event: CalendarEvent) -> CalendarEvent:
        calendar_event = event.with_calendar_identity(
            event_id=event_id,
            source_system=self.system,
            source_owner=self.owner,
        )
        remote_event = self.calendar.event_by_uid(event_id)
        remote_event.data = self.mapper.to_ical(calendar_event)
        remote_event.save(no_create=True)
        return calendar_event

    def delete_event(self, event_id: str) -> CalendarEvent:
        remote_event = self.calendar.event_by_uid(event_id)
        calendar_event = self.mapper.from_ical(remote_event.data, source_owner=self.owner)
        deleted = calendar_event.model_copy(update={"status": "deleted"})
        remote_event.data = self.mapper.to_ical(deleted)
        remote_event.save(no_create=True)
        return deleted

    def _generate_event_id(self) -> str:
        return f"yandex_{self.owner}_{uuid4().hex[:12]}"
