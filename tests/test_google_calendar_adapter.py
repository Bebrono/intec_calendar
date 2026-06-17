from datetime import datetime

from app.adapters import GoogleCalendarAdapter
from app.models import CalendarEvent


def test_google_calendar_adapter_crud_with_fake_service():
    service = FakeGoogleService()
    adapter = GoogleCalendarAdapter(service=service)
    event = CalendarEvent(
        id="",
        title="Smoke test",
        description="Temporary",
        start_time=datetime(2026, 6, 17, 10, 0, 0),
        end_time=datetime(2026, 6, 17, 10, 30, 0),
        organizer="calendar_sync_service",
        attendees=[],
        source_system="google",
        source_owner="developer_2",
        status="confirmed",
        updated_at=datetime(2026, 6, 17, 9, 0, 0),
    )

    created = adapter.create_event(event)
    updated = adapter.update_event(
        created.id,
        created.model_copy(update={"title": "Smoke test updated"}),
    )
    events = adapter.get_events()
    deleted = adapter.delete_event(updated.id)

    assert created.id == "google_event_1"
    assert updated.title == "Smoke test updated"
    assert [event.id for event in events] == ["google_event_1"]
    assert deleted.status == "deleted"


class FakeGoogleService:
    def __init__(self):
        self.resource = FakeEventsResource()

    def events(self):
        return self.resource


class FakeEventsResource:
    def __init__(self):
        self.items = {}
        self.counter = 0

    def list(self, **kwargs):
        return FakeRequest({"items": list(self.items.values())})

    def list_next(self, request, response):
        return None

    def insert(self, *, calendarId, body):
        self.counter += 1
        event_id = f"google_event_{self.counter}"
        payload = self._with_google_fields(event_id, body)
        self.items[event_id] = payload
        return FakeRequest(payload)

    def update(self, *, calendarId, eventId, body):
        payload = self._with_google_fields(eventId, body)
        self.items[eventId] = payload
        return FakeRequest(payload)

    def get(self, *, calendarId, eventId):
        return FakeRequest(self.items[eventId])

    def delete(self, *, calendarId, eventId):
        self.items.pop(eventId)
        return FakeRequest({})

    def _with_google_fields(self, event_id, body):
        payload = dict(body)
        payload.update(
            {
                "id": event_id,
                "updated": "2026-06-17T09:00:00Z",
                "creator": {"email": "owner@example.com"},
                "organizer": {"email": "owner@example.com"},
                "eventType": "default",
            }
        )
        return payload


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload
