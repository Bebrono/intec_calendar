from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.adapters import GoogleCalendarAdapter
from app.bootstrap import build_database, build_sync_adapters
from app.config import CALENDAR_ACCOUNTS, PROJECT_ROOT, ensure_project_dirs
from app.logger import configure_logger
from app.models import CalendarEvent
from app.services.google_calendar_config import (
    clear_sync_calendar,
    recreate_sync_calendar,
)
from app.services.google_oauth import build_calendar_service
from app.services.sync_service import SyncService


JSON_TO_GOOGLE_EVENT_ID = "outlook_live_google_demo_1"


def run_google_integration_demo(root: Path = PROJECT_ROOT) -> None:
    ensure_project_dirs(root)
    logger = configure_logger(root / "logs" / "sync.log")
    database = build_database(root)
    google_service = build_calendar_service(root)

    print("Integration demo setup: reset SQLite, JSON output, and Google test calendar")
    _reset_state(root, database, google_service, recreate_calendar=True)

    print("\nScenario 1: JSON -> Google")
    adapters = build_sync_adapters(root=root, use_real_google=True)
    manager = _find_adapter(adapters, owner="manager", system="outlook")
    google = _find_google_adapter(adapters)

    manager.create_event(
        CalendarEvent(
            id=JSON_TO_GOOGLE_EVENT_ID,
            title="Live JSON to Google",
            description="Created in Outlook JSON calendar",
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
    _run_sync(adapters, database, logger)
    _assert_google_title(google, "Live JSON to Google")
    print("- created Google copy")

    event = _find_event(manager.get_events(), JSON_TO_GOOGLE_EVENT_ID)
    manager.update_event(
        event.id,
        event.model_copy(
            update={
                "title": "Live JSON to Google Updated",
                "updated_at": datetime(2026, 6, 18, 9, 30, 0),
            }
        ),
    )
    _run_sync(adapters, database, logger)
    _assert_google_title(google, "Live JSON to Google Updated")
    print("- updated Google copy")

    event = _find_event(manager.get_events(), JSON_TO_GOOGLE_EVENT_ID)
    manager.update_event(
        event.id,
        event.model_copy(
            update={
                "status": "deleted",
                "updated_at": datetime(2026, 6, 18, 10, 0, 0),
            }
        ),
    )
    _run_sync(adapters, database, logger)
    _assert_google_deleted(google, "Live JSON to Google Updated")
    print("- propagated deletion to Google")

    print("\nScenario 2: Google -> JSON")
    _reset_state(root, database, google_service, recreate_calendar=True)
    adapters = build_sync_adapters(root=root, use_real_google=True)
    google = _find_google_adapter(adapters)

    google_created = google.create_event(
        CalendarEvent(
            id="",
            title="Live Google to JSON",
            description="Created in Google test calendar",
            start_time=datetime(2026, 6, 19, 10, 0, 0),
            end_time=datetime(2026, 6, 19, 11, 0, 0),
            organizer="developer_2",
            attendees=[],
            source_system="google",
            source_owner="developer_2",
            status="confirmed",
            updated_at=datetime(2026, 6, 19, 9, 0, 0),
        )
    )
    _run_sync(adapters, database, logger)
    _assert_json_title(adapters, "manager", "outlook", "Live Google to JSON")
    print("- created JSON copies")

    google_updated = google.update_event(
        google_created.id,
        google_created.model_copy(
            update={
                "title": "Live Google to JSON Updated",
                "updated_at": datetime(2026, 6, 19, 9, 30, 0),
            }
        ),
    )
    _run_sync(adapters, database, logger)
    _assert_json_title(adapters, "manager", "outlook", "Live Google to JSON Updated")
    print("- updated JSON copies")

    google.delete_event(google_updated.id)
    _run_sync(adapters, database, logger)
    _assert_json_deleted(adapters, "manager", "outlook")
    print("- propagated deletion to JSON")

    print("\nIntegration demo complete")


def _reset_state(
    root: Path,
    database,
    google_service,
    *,
    recreate_calendar: bool = False,
) -> None:
    database.reset_db()
    for account in CALENDAR_ACCOUNTS:
        (root / "data" / "output" / account.filename).write_text(
            "[]",
            encoding="utf-8",
        )
    if recreate_calendar:
        recreate_sync_calendar(google_service, root=root)
    else:
        clear_sync_calendar(google_service, root=root)


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


def _find_google_adapter(adapters) -> GoogleCalendarAdapter:
    adapter = _find_adapter(adapters, owner="developer_2", system="google")
    if not isinstance(adapter, GoogleCalendarAdapter):
        raise TypeError("developer_2/google adapter is not GoogleCalendarAdapter")
    return adapter


def _find_event(events: list[CalendarEvent], event_id: str) -> CalendarEvent:
    for event in events:
        if event.id == event_id:
            return event
    raise LookupError(f"Event {event_id} not found")


def _assert_google_title(adapter: GoogleCalendarAdapter, title: str) -> None:
    if not any(event.title == title and event.status == "confirmed" for event in adapter.get_events()):
        raise AssertionError(f"Google event {title!r} not found")


def _assert_google_deleted(adapter: GoogleCalendarAdapter, title: str) -> None:
    if not any(event.title == title and event.status == "deleted" for event in adapter.get_events()):
        raise AssertionError(f"Google event {title!r} is not marked deleted")


def _assert_json_title(adapters, owner: str, system: str, title: str) -> None:
    adapter = _find_adapter(adapters, owner=owner, system=system)
    if not any(event.title == title and event.status == "confirmed" for event in adapter.get_events()):
        raise AssertionError(f"JSON event {title!r} not found in {system}/{owner}")


def _assert_json_deleted(adapters, owner: str, system: str) -> None:
    adapter = _find_adapter(adapters, owner=owner, system=system)
    if not any(event.status == "deleted" for event in adapter.get_events()):
        raise AssertionError(f"No deleted JSON event found in {system}/{owner}")
