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
from app.storage.repositories import MappingRepository


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


def test_unmapped_deleted_event_is_ignored(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    for adapter in adapters:
        write_json(adapter.file_path, [])
    manager = find_adapter(adapters, owner="manager", system="outlook")
    manager.create_event(
        CalendarEvent(
            id="deleted_before_sync",
            title="Deleted before sync",
            description=None,
            start_time=datetime(2026, 6, 15, 15, 0, 0),
            end_time=datetime(2026, 6, 15, 16, 0, 0),
            organizer="manager",
            attendees=["developer_1", "developer_2", "leader"],
            source_system="outlook",
            source_owner="manager",
            status="deleted",
            updated_at=datetime(2026, 6, 15, 12, 0, 0),
        )
    )
    service = build_service(adapters, database)

    result = service.sync()

    assert result.groups_processed == 0
    assert result.events_created == 0
    for adapter in adapters:
        events = adapter.get_events()
        if adapter is manager:
            assert len(events) == 1
            assert events[0].status == "deleted"
        else:
            assert events == []


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

def test_update_from_synced_copy_becomes_canonical(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)
    service.sync()

    google = find_adapter(adapters, owner="developer_2", system="google")
    event = google.get_events()[0]
    google.update_event(
        event.id,
        event.model_copy(
            update={
                "title": "Updated from Google copy",
                "start_time": datetime(2026, 6, 15, 18, 0, 0),
                "end_time": datetime(2026, 6, 15, 19, 0, 0),
                "updated_at": datetime(2026, 6, 15, 13, 30, 0),
            }
        ),
    )

    result = service.sync()

    assert result.events_updated == 3
    for adapter in adapters:
        event = adapter.get_events()[0]
        assert event.title == "Updated from Google copy"
        assert event.start_time == datetime(2026, 6, 15, 18, 0, 0)


def test_deleted_event_is_propagated(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)
    service.sync()

    manager = find_adapter(adapters, owner="manager", system="outlook")
    event = manager.get_events()[0]
    manager.delete_event(event.id)

    result = service.sync()

    assert result.events_deleted == 3
    for adapter in adapters:
        assert adapter.get_events() == []

    second_result = service.sync()

    assert second_result.events_deleted == 0


def test_stale_terminal_event_still_deletes_whole_group(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)
    service.sync()

    google = find_adapter(adapters, owner="developer_2", system="google")
    event = google.get_events()[0]
    google.delete_event(event.id)

    result = service.sync()

    assert result.events_created == 0
    assert result.events_deleted == 3
    for adapter in adapters:
        assert adapter.get_events() == []


def test_terminal_mapping_deletes_group_even_if_copy_is_missing(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)
    service.sync()

    google = find_adapter(adapters, owner="developer_2", system="google")
    removed_event_id = google.get_events()[0].id
    write_json(
        google.file_path,
        [
            item
            for item in json.loads(google.file_path.read_text(encoding="utf-8"))
            if item["id"] != removed_event_id
        ],
    )
    with database.SessionLocal() as session:
        mappings = MappingRepository(session)
        mapping = mappings.get_by_external_event(
            calendar_owner="developer_2",
            calendar_system="google",
            external_event_id=removed_event_id,
        )
        assert mapping is not None
        mappings.update_mapping(
            mapping,
            status="deleted",
            last_event_updated_at=datetime(2026, 6, 15, 13, 0, 0),
        )
        session.commit()

    result = service.sync()

    assert result.events_created == 0
    assert result.events_deleted == 3
    assert google.get_events() == []
    for adapter in adapters:
        if adapter is google:
            continue
        assert adapter.get_events() == []


def test_missing_mapped_event_is_treated_as_manual_delete(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)
    service.sync()

    google = find_adapter(adapters, owner="developer_2", system="google")
    removed_event_id = google.get_events()[0].id
    write_json(
        google.file_path,
        [
            item
            for item in json.loads(google.file_path.read_text(encoding="utf-8"))
            if item["id"] != removed_event_id
        ],
    )

    result = service.sync()

    assert result.events_created == 0
    assert result.events_deleted == 3
    assert google.get_events() == []
    for adapter in adapters:
        if adapter is google:
            continue
        assert adapter.get_events() == []


def test_missing_mapped_event_does_not_create_duplicates_on_next_sync(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    service = build_service(adapters, database)
    service.sync()

    yandex = find_adapter(adapters, owner="developer_1", system="yandex")
    removed_event_id = yandex.get_events()[0].id
    write_json(
        yandex.file_path,
        [
            item
            for item in json.loads(yandex.file_path.read_text(encoding="utf-8"))
            if item["id"] != removed_event_id
        ],
    )

    service.sync()
    result = service.sync()

    assert result.events_created == 0
    assert yandex.get_events() == []
    for adapter in adapters:
        if adapter is yandex:
            continue
        assert adapter.get_events() == []


def test_event_disappearing_during_update_is_treated_as_manual_delete(tmp_path):
    adapters, database = build_test_environment(tmp_path)
    yandex = find_adapter(adapters, owner="developer_1", system="yandex")
    vanishing_yandex = VanishingOnUpdateFileCalendarAdapter(
        file_path=yandex.file_path,
        owner=yandex.owner,
        system=yandex.system,
        mapper=yandex.mapper,
    )
    adapters[adapters.index(yandex)] = vanishing_yandex
    service = build_service(adapters, database)
    service.sync()

    vanishing_yandex.disappear_on_update_id = vanishing_yandex.get_events()[0].id
    manager = find_adapter(adapters, owner="manager", system="outlook")
    manager_event = manager.get_events()[0]
    manager.update_event(
        manager_event.id,
        manager_event.model_copy(
            update={
                "title": "Updated while Yandex event disappears",
                "updated_at": datetime(2026, 6, 15, 13, 30, 0),
            }
        ),
    )

    result = service.sync()

    assert result.events_created == 0
    assert vanishing_yandex.get_events() == []
    for adapter in adapters:
        if adapter is vanishing_yandex:
            continue
        assert adapter.get_events() == []


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


class VanishingOnUpdateFileCalendarAdapter(FileCalendarAdapter):
    disappear_on_update_id: str | None = None

    def update_event(self, event_id: str, event: CalendarEvent) -> CalendarEvent:
        if event_id == self.disappear_on_update_id:
            raw_events = [
                item for item in self._read_raw_events() if item.get("id") != event_id
            ]
            self._write_raw_events(raw_events)
            raise KeyError(f"Event {event_id!r} not found in {self.file_path}")
        return super().update_event(event_id, event)
