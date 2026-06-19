from datetime import datetime

from app.models import CalendarEvent
from app.services.yandex_event_mapper import (
    SYNC_ATTENDEES_KEY,
    SYNC_ORGANIZER_KEY,
    SYNC_STATUS_KEY,
    SYNC_UPDATED_AT_KEY,
    YandexEventMapper,
)


def test_calendar_event_is_converted_to_ical_payload():
    mapper = YandexEventMapper()
    event = CalendarEvent(
        id="event_1",
        title="Yandex event",
        description="Planning",
        start_time=datetime(2026, 6, 22, 10, 0, 0),
        end_time=datetime(2026, 6, 22, 11, 0, 0),
        organizer="manager",
        attendees=["developer_1", "developer_2"],
        source_system="yandex",
        source_owner="developer_1",
        status="confirmed",
        updated_at=datetime(2026, 6, 22, 9, 0, 0),
    )

    payload = mapper.to_ical(event)

    assert "UID:event_1" in payload
    assert "SUMMARY:Yandex event" in payload
    assert f"{SYNC_UPDATED_AT_KEY}:2026-06-22T09:00:00" in payload
    assert f"{SYNC_ORGANIZER_KEY}:manager" in payload
    assert f"{SYNC_STATUS_KEY}:confirmed" in payload
    assert SYNC_ATTENDEES_KEY in payload


def test_deleted_calendar_event_is_converted_to_cancelled_ical_payload():
    mapper = YandexEventMapper()
    event = CalendarEvent(
        id="event_1",
        title="Yandex event",
        description="Planning",
        start_time=datetime(2026, 6, 22, 10, 0, 0),
        end_time=datetime(2026, 6, 22, 11, 0, 0),
        organizer="manager",
        attendees=[],
        source_system="yandex",
        source_owner="developer_1",
        status="deleted",
        updated_at=datetime(2026, 6, 22, 9, 0, 0),
    )

    payload = mapper.to_ical(event)

    assert "STATUS:CANCELLED" in payload
    assert f"{SYNC_STATUS_KEY}:deleted" in payload


def test_ical_payload_is_converted_to_calendar_event():
    mapper = YandexEventMapper()
    payload = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:event_1
SUMMARY:Yandex event
DESCRIPTION:Created in Yandex
DTSTART:20260622T100000
DTEND:20260622T110000
STATUS:CANCELLED
X-CALENDAR-SYNC-STATUS:deleted
X-CALENDAR-SYNC-UPDATED-AT:2026-06-22T09:30:00
X-CALENDAR-SYNC-ORGANIZER:developer_1
X-CALENDAR-SYNC-ATTENDEES:["developer_2"]
END:VEVENT
END:VCALENDAR
"""

    event = mapper.from_ical(payload, source_owner="developer_1")

    assert event.id == "event_1"
    assert event.title == "Yandex event"
    assert event.description == "Created in Yandex"
    assert event.status == "deleted"
    assert event.organizer == "developer_1"
    assert event.attendees == ["developer_2"]
    assert event.updated_at == datetime(2026, 6, 22, 9, 30, 0)


def test_manual_yandex_cancel_overrides_stale_sync_metadata():
    mapper = YandexEventMapper()
    payload = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:event_1
SUMMARY:Yandex event
DESCRIPTION:Created in Yandex\\n\\n[SYNC_STATUS: confirmed]\\n[SYNC_UPDATED_AT: 2026-06-22T09:30:00]
DTSTART:20260622T100000
DTEND:20260622T110000
STATUS:CANCELLED
LAST-MODIFIED:20260622T120000Z
END:VEVENT
END:VCALENDAR
"""

    event = mapper.from_ical(payload, source_owner="developer_1")

    assert event.status == "deleted"
    assert event.updated_at == datetime(2026, 6, 22, 17, 0, 0)
