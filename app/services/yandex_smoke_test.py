from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from caldav import Calendar

from app.adapters import YandexCalendarAdapter
from app.models import CalendarEvent
from app.services.google_event_mapper import DEFAULT_TIMEZONE


@dataclass
class YandexSmokeTestResult:
    created_event_id: str
    created_title: str
    updated_title: str
    deleted_status: str


def run_yandex_smoke_test(
    calendar: Calendar,
    *,
    owner: str = "developer_1",
) -> YandexSmokeTestResult:
    adapter = YandexCalendarAdapter(calendar=calendar, owner=owner)
    now = datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).replace(microsecond=0, tzinfo=None)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(minutes=30)

    created = adapter.create_event(
        CalendarEvent(
            id="",
            title="Calendar Sync Yandex Smoke Test",
            description="Temporary event created by Calendar Sync Service.",
            start_time=start_time,
            end_time=end_time,
            organizer="calendar_sync_service",
            attendees=[],
            source_system="yandex",
            source_owner=adapter.owner,
            status="confirmed",
            updated_at=now,
        )
    )
    updated = adapter.update_event(
        created.id,
        created.model_copy(
            update={
                "title": "Calendar Sync Yandex Smoke Test Updated",
                "description": "Temporary event updated by Calendar Sync Service.",
                "updated_at": datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).replace(
                    microsecond=0,
                    tzinfo=None,
                ),
            }
        ),
    )
    deleted = adapter.delete_event(updated.id)

    return YandexSmokeTestResult(
        created_event_id=created.id,
        created_title=created.title,
        updated_title=updated.title,
        deleted_status=deleted.status,
    )
