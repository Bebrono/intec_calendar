import json
from datetime import datetime
from app.models import CalendarEvent
from app.services.google_event_mapper import (
    DEFAULT_TIMEZONE,
    SYNC_ATTENDEES_KEY,
    SYNC_ORGANIZER_KEY,
    SYNC_STATUS_KEY,
    SYNC_UPDATED_AT_KEY,
    GoogleEventMapper,
)


def test_calendar_event_is_converted_to_google_payload():
    mapper = GoogleEventMapper()
    event = CalendarEvent(
        id="local_1",
        title="Sync meeting",
        description="Planning",
        start_time=datetime(2026, 6, 17, 10, 0, 0),
        end_time=datetime(2026, 6, 17, 11, 0, 0),
        organizer="manager",
        attendees=["dev@example.com", "developer_1"],
        source_system="google",
        source_owner="developer_2",
        status="confirmed",
        updated_at=datetime(2026, 6, 17, 9, 0, 0),
    )

    payload = mapper.to_google(event)

    assert payload["summary"] == "Sync meeting"
    assert payload["description"] == "Planning"
    assert payload["start"]["timeZone"] == DEFAULT_TIMEZONE
    assert payload["attendees"] == [{"email": "dev@example.com"}]
    assert (
        payload["extendedProperties"]["private"][SYNC_UPDATED_AT_KEY]
        == "2026-06-17T09:00:00"
    )
    assert payload["extendedProperties"]["private"][SYNC_ORGANIZER_KEY] == "manager"
    assert (
        json.loads(payload["extendedProperties"]["private"][SYNC_ATTENDEES_KEY])
        == ["dev@example.com", "developer_1"]
    )
    assert payload["extendedProperties"]["private"][SYNC_STATUS_KEY] == "confirmed"


def test_google_payload_is_converted_to_calendar_event():
    mapper = GoogleEventMapper()
    payload = {
        "id": "google_1",
        "summary": "Google event",
        "description": "Created in Google",
        "start": {"dateTime": "2026-06-17T10:00:00+05:00"},
        "end": {"dateTime": "2026-06-17T11:00:00+05:00"},
        "creator": {"email": "owner@example.com"},
        "attendees": [{"email": "dev@example.com"}],
        "status": "cancelled",
        "updated": "2026-06-17T09:00:00Z",
        "extendedProperties": {
            "private": {
                SYNC_UPDATED_AT_KEY: "2026-06-17T09:30:00",
                SYNC_ORGANIZER_KEY: "manager",
                SYNC_ATTENDEES_KEY: '["developer_1", "dev@example.com"]',
                SYNC_STATUS_KEY: "confirmed",
            }
        },
    }

    event = mapper.from_google(payload, source_owner="developer_2")

    assert event.id == "google_1"
    assert event.title == "Google event"
    assert event.status == "deleted"
    assert event.organizer == "manager"
    assert event.attendees == ["developer_1", "dev@example.com"]
    assert event.source_system == "google"
    assert event.start_time == datetime(2026, 6, 17, 10, 0, 0)
    assert event.updated_at == datetime(2026, 6, 17, 14, 0, 0)
