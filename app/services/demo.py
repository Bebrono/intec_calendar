from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.bootstrap import build_database, build_file_adapters
from app.config import CALENDAR_ACCOUNTS, PROJECT_ROOT, ensure_project_dirs
from app.logger import configure_logger
from app.models import CalendarEvent
from app.services.sync_service import SyncService


DEMO_EVENT_ID = "outlook_demo_event_1"


def run_demo(root: Path = PROJECT_ROOT) -> None:
    ensure_project_dirs(root)
    _reset_demo_state(root)

    logger = configure_logger(root / "logs" / "sync.log")
    database = build_database(root)
    database.reset_db()
    adapters = build_file_adapters(root=root)
    manager_adapter = _find_adapter(adapters, owner="manager", system="outlook")

    manager_adapter.create_event(
        CalendarEvent(
            id=DEMO_EVENT_ID,
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

    print("Demo step 1: create event in Outlook and synchronize")
    _run_sync(adapters, database, logger)
    _print_calendar_state(adapters)

    event = _get_demo_event(manager_adapter)
    manager_adapter.update_event(
        event.id,
        event.model_copy(
            update={
                "title": "Командная встреча: планирование спринта",
                "start_time": datetime(2026, 6, 15, 16, 0, 0),
                "end_time": datetime(2026, 6, 15, 17, 0, 0),
                "updated_at": datetime(2026, 6, 15, 13, 0, 0),
            }
        ),
    )

    print("\nDemo step 2: update event in Outlook and synchronize")
    _run_sync(adapters, database, logger)
    _print_calendar_state(adapters)

    event = _get_demo_event(manager_adapter)
    manager_adapter.delete_event(event.id)

    print("\nDemo step 3: delete event and synchronize")
    _run_sync(adapters, database, logger)
    _print_calendar_state(adapters)


def _reset_demo_state(root: Path) -> None:
    for account in CALENDAR_ACCOUNTS:
        (root / "data" / "output" / account.filename).write_text(
            "[]",
            encoding="utf-8",
        )

    db_path = root / "data" / "sync.db"
    if db_path.exists():
        db_path.unlink()

    log_path = root / "logs" / "sync.log"
    log_path.write_text("", encoding="utf-8")


def _run_sync(adapters, database, logger) -> None:
    result = SyncService(
        adapters=adapters,
        database=database,
        logger=logger,
    ).sync()
    print(
        "Result: "
        f"groups={result.groups_processed}, "
        f"created={result.events_created}, "
        f"updated={result.events_updated}, "
        f"deleted={result.events_deleted}"
    )


def _print_calendar_state(adapters) -> None:
    for adapter in adapters:
        events = adapter.get_events()
        titles = ", ".join(f"{event.title} ({event.status})" for event in events)
        print(f"- {adapter.system}/{adapter.owner}: {titles or 'no events'}")


def _find_adapter(adapters, *, owner: str, system: str):
    for adapter in adapters:
        if adapter.owner == owner and adapter.system == system:
            return adapter
    raise LookupError(f"Adapter {system}/{owner} not found")


def _get_demo_event(manager_adapter) -> CalendarEvent:
    for event in manager_adapter.get_events():
        if event.id == DEMO_EVENT_ID:
            return event
    raise LookupError("Demo event not found")
