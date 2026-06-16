import json
import logging
from datetime import datetime
from pathlib import Path

from app.adapters import FileCalendarAdapter
from app.config import CALENDAR_ACCOUNTS
from app.models import CalendarEvent
from app.services.event_mapper import EventMapper
from app.services.sync_service import SyncService
from app.storage import Database


def test_new_event_is_copied_to_all_calendars(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)

    result = service.sync()

    assert result.groups_processed == 1
    assert result.events_created == 3
    for adapter in adapters:
        events = adapter.get_events()
        assert len(events) == 1
        assert events[0].title == "Командная встреча"
        assert EventMapper().extract_sync_id(events[0].description)


def test_second_sync_does_not_create_duplicates(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)

    service.sync()
    result = service.sync()

    assert result.events_created == 0
    for adapter in adapters:
        assert len(adapter.get_events()) == 1


def test_updated_event_is_propagated(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)
    service.sync()

    manager = find_adapter(adapters, owner="manager", system="outlook")
    event = manager.get_events()[0]
    manager.update_event(
        event.id,
        event.model_copy(
            update={
                "title": "Обновленная командная встреча",
                "start_time": datetime(2026, 6, 15, 16, 0, 0),
                "end_time": datetime(2026, 6, 15, 17, 0, 0),
                "updated_at": datetime(2026, 6, 15, 13, 0, 0),
            }
        ),
    )

    result = service.sync()

    assert result.events_updated == 3
    for adapter in adapters:
        event = adapter.get_events()[0]
        assert event.title == "Обновленная командная встреча"
        assert event.start_time == datetime(2026, 6, 15, 16, 0, 0)


def test_deleted_event_is_propagated(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)
    service.sync()

    manager = find_adapter(adapters, owner="manager", system="outlook")
    event = manager.get_events()[0]
    manager.update_event(
        event.id,
        event.model_copy(
            update={
                "status": "deleted",
                "updated_at": datetime(2026, 6, 15, 14, 0, 0),
            }
        ),
    )

    result = service.sync()

    assert result.events_deleted == 3
    for adapter in adapters:
        assert adapter.get_events()[0].status == "deleted"


def build_test_environment(tmp_path: Path):
    calendar_dir = tmp_path / "calendars"
    calendar_dir.mkdir()
    mapper = EventMapper()
    adapters = [
        FileCalendarAdapter(
            file_path=calendar_dir / account.filename,
            owner=account.owner,
            system=account.system,
            mapper=mapper,
        )
        for account in CALENDAR_ACCOUNTS
    ]

    for adapter in adapters:
        write_json(adapter.file_path, [])

    manager = find_adapter(adapters, owner="manager", system="outlook")
    manager.create_event(
        CalendarEvent(
            id="outlook_event_1",
            title="Командная встреча",
            description="Обсуждение задач на неделю",
            start_time=datetime(2026, 6, 15, 15, 0, 0),
            end_time=datetime(2026, 6, 15, 16, 0, 0),
            organizer="manager",
            attendees=["developer_1", "developer_2", "leader"],
            source_system="outlook",
            source_owner="manager",
            status="confirmed",
            updated_at=datetime(2026, 6, 15, 12, 0, 0),
        )
    )
    return adapters, Database(tmp_path / "sync.db")


def build_service(adapters, database):
    logger = logging.getLogger("calendar_sync_test")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return SyncService(adapters=adapters, database=database, logger=logger)


def find_adapter(adapters, *, owner: str, system: str):
    for adapter in adapters:
        if adapter.owner == owner and adapter.system == system:
            return adapter
    raise LookupError(f"Adapter {system}/{owner} not found")


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
