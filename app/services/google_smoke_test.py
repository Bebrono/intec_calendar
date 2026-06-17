from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.adapters import GoogleCalendarAdapter
from app.models import CalendarEvent
from app.services.google_event_mapper import DEFAULT_TIMEZONE


@dataclass
class GoogleSmokeTestResult:
    created_event_id: str
    created_title: str
    updated_title: str
    deleted_status: str


def run_google_smoke_test(service, *, calendar_id: str = "primary") -> GoogleSmokeTestResult:
    adapter = GoogleCalendarAdapter(service=service, calendar_id=calendar_id)
    now = datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).replace(microsecond=0)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(minutes=30)

    created = adapter.create_event(
        CalendarEvent(
            id="",
            title="Calendar Sync Smoke Test",
            description="Temporary event created by Calendar Sync Service.",
            start_time=start_time,
            end_time=end_time,
            organizer="calendar_sync_service",
            attendees=[],
            source_system="google",
            source_owner=adapter.owner,
            status="confirmed",
            updated_at=now,
        )
    )

    updated = adapter.update_event(
        created.id,
        created.model_copy(
            update={
                "title": "Calendar Sync Smoke Test Updated",
                "description": "Temporary event updated by Calendar Sync Service.",
                "updated_at": datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).replace(
                    microsecond=0
                ),
            }
        ),
    )
    deleted = adapter.delete_event(updated.id)

    return GoogleSmokeTestResult(
        created_event_id=created.id,
        created_title=created.title,
        updated_title=updated.title,
        deleted_status=deleted.status,
    )
