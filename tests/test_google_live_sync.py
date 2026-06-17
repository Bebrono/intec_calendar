import logging
from datetime import datetime

from app.adapters import GoogleCalendarAdapter
from app.bootstrap import build_sync_adapters
from app.config import CALENDAR_ACCOUNTS
from app.models import CalendarEvent
from app.services.google_calendar_config import (
    GoogleCalendarConfig,
    create_sync_calendar,
    recreate_sync_calendar,
    save_sync_calendar_config,
)
from app.services.sync_service import SyncService
from app.storage import Database


def test_create_sync_calendar_saves_config(tmp_path):
    service = FakeGoogleService()

    result = create_sync_calendar(service, root=tmp_path, summary="Test Sync Calendar")

    assert result.created is True
    assert result.config.summary == "Test Sync Calendar"
    assert result.config.calendar_id == "calendar_1"
    assert (tmp_path / "data" / "google_calendar_config.json").exists()


def test_recreate_sync_calendar_replaces_existing_config(tmp_path):
    service = FakeGoogleService()
    save_sync_calendar_config(
        GoogleCalendarConfig(calendar_id="old_calendar", summary="Old"),
        tmp_path,
    )
    service.calendars_resource.items["old_calendar"] = {
        "id": "old_calendar",
        "summary": "Old",
    }

    result = recreate_sync_calendar(service, root=tmp_path, summary="New Calendar")

    assert result.created is True
    assert result.config.calendar_id == "calendar_1"
    assert "old_calendar" not in service.calendars_resource.items


def test_build_sync_adapters_replaces_google_file_adapter(tmp_path, monkeypatch):
    service = FakeGoogleService()
    save_sync_calendar_config(
        GoogleCalendarConfig(calendar_id="calendar_1", summary="Test"),
        tmp_path,
    )
    monkeypatch.setattr("app.bootstrap.build_calendar_service", lambda root: service)

    adapters = build_sync_adapters(root=tmp_path, use_real_google=True)

    assert any(isinstance(adapter, GoogleCalendarAdapter) for adapter in adapters)
    assert len(adapters) == len(CALENDAR_ACCOUNTS)
    assert not any(
        adapter.owner == "developer_2"
        and adapter.system == "google"
        and not isinstance(adapter, GoogleCalendarAdapter)
        for adapter in adapters
    )


def test_real_google_sync_creates_google_copy_with_fake_service(tmp_path, monkeypatch):
    service = FakeGoogleService()
    save_sync_calendar_config(
        GoogleCalendarConfig(calendar_id="calendar_1", summary="Test"),
        tmp_path,
    )
    monkeypatch.setattr("app.bootstrap.build_calendar_service", lambda root: service)
    adapters = build_sync_adapters(root=tmp_path, use_real_google=True)
    manager = find_adapter(adapters, owner="manager", system="outlook")
    manager.create_event(
        CalendarEvent(
            id="outlook_event_1",
            title="Manager event",
            description="From JSON",
            start_time=datetime(2026, 6, 18, 10, 0, 0),
            end_time=datetime(2026, 6, 18, 11, 0, 0),
            organizer="manager",
            attendees=["developer_1", "developer_2", "leader"],
            source_system="outlook",
            source_owner="manager",
            status="confirmed",
            updated_at=datetime(2026, 6, 18, 9, 0, 0),
        )
    )

    result = SyncService(
        adapters=adapters,
        database=Database(tmp_path / "sync.db"),
        logger=logging.getLogger("google_live_sync_test"),
    ).sync()

    google = find_adapter(adapters, owner="developer_2", system="google")
    assert result.events_created == 3
    assert [event.title for event in google.get_events()] == ["Manager event"]


def find_adapter(adapters, *, owner: str, system: str):
    for adapter in adapters:
        if adapter.owner == owner and adapter.system == system:
            return adapter
    raise LookupError(f"Adapter {system}/{owner} not found")


class FakeGoogleService:
    def __init__(self):
        self.events_resource = FakeEventsResource()
        self.calendars_resource = FakeCalendarsResource()

    def events(self):
        return self.events_resource

    def calendars(self):
        return self.calendars_resource


class FakeCalendarsResource:
    def __init__(self):
        self.items = {}
        self.counter = 0

    def insert(self, *, body):
        self.counter += 1
        calendar_id = f"calendar_{self.counter}"
        payload = {"id": calendar_id, "summary": body["summary"]}
        self.items[calendar_id] = payload
        return FakeRequest(payload)

    def delete(self, *, calendarId):
        self.items.pop(calendarId, None)
        return FakeRequest({})


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
        self.items.pop(eventId, None)
        return FakeRequest({})

    def _with_google_fields(self, event_id, body):
        payload = dict(body)
        payload.update(
            {
                "id": event_id,
                "updated": "2026-06-18T09:00:00Z",
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
