from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.adapters import YandexCalendarAdapter
from app.bootstrap import build_database, build_sync_adapters
from app.config import CALENDAR_ACCOUNTS, PROJECT_ROOT, ensure_project_dirs
from app.logger import configure_logger
from app.models import CalendarEvent
from app.services.sync_service import SyncService
from app.services.yandex_calendar_config import (
    build_yandex_client,
    clear_sync_calendar,
    load_sync_calendar,
)


JSON_TO_YANDEX_EVENT_ID = "outlook_live_yandex_demo_1"


def run_yandex_integration_demo(root: Path = PROJECT_ROOT) -> None:
    ensure_project_dirs(root)
    logger = configure_logger(root / "logs" / "sync.log")
    database = build_database(root)
    yandex_client = build_yandex_client(root)

    print("Integration demo setup: reset SQLite, JSON output, and Yandex test calendar")
    _reset_state(root, database, yandex_client)

    print("\nScenario 1: JSON -> Yandex")
    adapters = build_sync_adapters(root=root, use_real_yandex=True)
    manager = _find_adapter(adapters, owner="manager", system="outlook")
    yandex = _find_yandex_adapter(adapters)

    manager.create_event(
        CalendarEvent(
            id=JSON_TO_YANDEX_EVENT_ID,
            title="Live JSON to Yandex",
            description="Created in Outlook JSON calendar",
            start_time=datetime(2026, 6, 20, 10, 0, 0),
            end_time=datetime(2026, 6, 20, 11, 0, 0),
            organizer="manager",
            attendees=["developer_1", "developer_2", "leader"],
            source_system="outlook",
            source_owner="manager",
            status="confirmed",
            updated_at=datetime(2026, 6, 20, 9, 0, 0),
        )
    )
    _run_sync(adapters, database, logger)
    _assert_yandex_title(yandex, "Live JSON to Yandex")
    print("- created Yandex copy")

    event = _find_event(manager.get_events(), JSON_TO_YANDEX_EVENT_ID)
    manager.update_event(
        event.id,
        event.model_copy(
            update={
                "title": "Live JSON to Yandex Updated",
                "updated_at": datetime(2026, 6, 20, 9, 30, 0),
            }
        ),
    )
    _run_sync(adapters, database, logger)
    _assert_yandex_title(yandex, "Live JSON to Yandex Updated")
    print("- updated Yandex copy")

    event = _find_event(manager.get_events(), JSON_TO_YANDEX_EVENT_ID)
    manager.update_event(
        event.id,
        event.model_copy(
            update={
                "status": "deleted",
                "updated_at": datetime(2026, 6, 20, 10, 0, 0),
            }
        ),
    )
    _run_sync(adapters, database, logger)
    _assert_yandex_deleted(yandex, "Live JSON to Yandex Updated")
    print("- propagated deletion to Yandex")

    print("\nScenario 2: Yandex -> JSON")
    _reset_state(root, database, yandex_client)
    adapters = build_sync_adapters(root=root, use_real_yandex=True)
    yandex = _find_yandex_adapter(adapters)

    yandex_created = yandex.create_event(
        CalendarEvent(
            id="",
            title="Live Yandex to JSON",
            description="Created in Yandex test calendar",
            start_time=datetime(2026, 6, 21, 10, 0, 0),
            end_time=datetime(2026, 6, 21, 11, 0, 0),
            organizer="developer_1",
            attendees=[],
            source_system="yandex",
            source_owner="developer_1",
            status="confirmed",
            updated_at=datetime(2026, 6, 21, 9, 0, 0),
        )
    )
    _run_sync(adapters, database, logger)
    _assert_json_title(adapters, "manager", "outlook", "Live Yandex to JSON")
    print("- created JSON copies")

    yandex_updated = yandex.update_event(
        yandex_created.id,
        yandex_created.model_copy(
            update={
                "title": "Live Yandex to JSON Updated",
                "updated_at": datetime(2026, 6, 21, 9, 30, 0),
            }
        ),
    )
    _run_sync(adapters, database, logger)
    _assert_json_title(adapters, "manager", "outlook", "Live Yandex to JSON Updated")
    print("- updated JSON copies")

    yandex.delete_event(yandex_updated.id)
    _run_sync(adapters, database, logger)
    _assert_json_deleted(adapters, "manager", "outlook")
    print("- propagated deletion to JSON")

    print("\nYandex integration demo complete")


def _reset_state(root: Path, database, yandex_client) -> None:
    database.reset_db()
    for account in CALENDAR_ACCOUNTS:
        (root / "data" / "output" / account.filename).write_text(
            "[]",
            encoding="utf-8",
        )
    clear_sync_calendar(yandex_client, root=root)


def _run_sync(adapters, database, logger) -> None:
    result = SyncService(
        adapters=adapters,
        database=database,
        logger=logger,
    ).sync()
    print(
        "  sync: "
        f"groups={result.groups_processed}, "
        f"created={result.events_created}, "
        f"updated={result.events_updated}, "
        f"deleted={result.events_deleted}"
    )


def _find_adapter(adapters, *, owner: str, system: str):
    for adapter in adapters:
        if adapter.owner == owner and adapter.system == system:
            return adapter
    raise LookupError(f"Adapter {system}/{owner} not found")


def _find_yandex_adapter(adapters) -> YandexCalendarAdapter:
    adapter = _find_adapter(adapters, owner="developer_1", system="yandex")
    if not isinstance(adapter, YandexCalendarAdapter):
        raise TypeError("developer_1/yandex adapter is not YandexCalendarAdapter")
    return adapter


def _find_event(events: list[CalendarEvent], event_id: str) -> CalendarEvent:
    for event in events:
        if event.id == event_id:
            return event
    raise LookupError(f"Event {event_id} not found")


def _assert_yandex_title(adapter: YandexCalendarAdapter, title: str) -> None:
    if not any(
        event.title == title and event.status == "confirmed"
        for event in adapter.get_events()
    ):
        raise AssertionError(f"Yandex event {title!r} not found")


def _assert_yandex_deleted(adapter: YandexCalendarAdapter, title: str) -> None:
    if not any(
        event.title == title and event.status == "deleted"
        for event in adapter.get_events()
    ):
        raise AssertionError(f"Yandex event {title!r} is not marked deleted")


def _assert_json_title(adapters, owner: str, system: str, title: str) -> None:
    adapter = _find_adapter(adapters, owner=owner, system=system)
    if not any(
        event.title == title and event.status == "confirmed"
        for event in adapter.get_events()
    ):
        raise AssertionError(f"JSON event {title!r} not found in {system}/{owner}")


def _assert_json_deleted(adapters, owner: str, system: str) -> None:
    adapter = _find_adapter(adapters, owner=owner, system=system)
    if not any(event.status == "deleted" for event in adapter.get_events()):
        raise AssertionError(f"No deleted JSON event found in {system}/{owner}")
