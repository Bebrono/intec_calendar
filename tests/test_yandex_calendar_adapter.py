from datetime import datetime

from app.adapters import YandexCalendarAdapter
from app.models import CalendarEvent


def test_yandex_calendar_adapter_crud_with_fake_calendar():
    calendar = FakeCalDAVCalendar()
    adapter = YandexCalendarAdapter(calendar=calendar)
    event = CalendarEvent(
        id="",
        title="Smoke test",
        description="Temporary",
        start_time=datetime(2026, 6, 22, 10, 0, 0),
        end_time=datetime(2026, 6, 22, 10, 30, 0),
        organizer="calendar_sync_service",
        attendees=[],
        source_system="yandex",
        source_owner="developer_1",
        status="confirmed",
        updated_at=datetime(2026, 6, 22, 9, 0, 0),
    )

    created = adapter.create_event(event)
    updated = adapter.update_event(
        created.id,
        created.model_copy(update={"title": "Smoke test updated"}),
    )
    events = adapter.get_events()
    deleted = adapter.delete_event(updated.id)

    assert created.id.startswith("yandex_developer_1_")
    assert updated.title == "Smoke test updated"
    assert [event.id for event in events] == [created.id]
    assert deleted.status == "deleted"


class FakeCalDAVCalendar:
    def __init__(self):
        self.items = {}

    def events(self):
        return list(self.items.values())

    def save_event(self, ical, no_overwrite=False):
        resource = FakeCalDAVEvent(ical, self)
        uid = resource.uid
        if no_overwrite and uid in self.items:
            raise RuntimeError(f"Event {uid} already exists")
        self.items[uid] = resource
        return resource

    def event_by_uid(self, uid):
        return self.items[uid]


class FakeCalDAVEvent:
    def __init__(self, data, calendar):
        self.data = data
        self.calendar = calendar

    @property
    def uid(self):
        for line in self.data.splitlines():
            if line.startswith("UID:"):
                return line.removeprefix("UID:")
        raise ValueError("UID not found")

    def save(self, no_create=False):
        self.calendar.items[self.uid] = self
        return self

    def delete(self):
        self.calendar.items.pop(self.uid, None)
