from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from app.adapters import CalendarAdapter
from app.bootstrap import build_database, build_sync_adapters
from app.config import CALENDAR_ACCOUNTS, PROJECT_ROOT, ensure_project_dirs
from app.models import CalendarEvent
from app.services.google_calendar_config import (
    clear_sync_calendar as clear_google_sync_calendar,
    create_sync_calendar as create_google_sync_calendar,
    load_sync_calendar_config as load_google_sync_calendar_config,
)
from app.services.google_oauth import TOKEN_PATH, build_calendar_service
from app.services.sync_service import SyncService
from app.services.yandex_calendar_config import (
    build_yandex_client,
    clear_sync_calendar as clear_yandex_sync_calendar,
    create_sync_calendar as create_yandex_sync_calendar,
    load_sync_calendar_config as load_yandex_sync_calendar_config,
    load_yandex_credentials,
)
from app.storage import Database


class LiveDemoError(RuntimeError):
    pass


class LiveDemoPrerequisiteError(LiveDemoError):
    pass


class LiveLinksError(LiveDemoError):
    pass


@dataclass(frozen=True)
class LiveDemoResult:
    lines: tuple[str, ...]


@dataclass(frozen=True)
class LiveCalendarLinks:
    google_url: str
    yandex_url: str
    yandex_calendar_name: str
    json_paths: tuple[Path, ...]


@dataclass(frozen=True)
class LiveDemoDependencies:
    adapter_builder: Callable[..., list[CalendarAdapter]] = build_sync_adapters
    database_builder: Callable[[Path], Database] = build_database
    logger_factory: Callable[[Path], logging.Logger] = lambda log_file: configure_live_demo_logger(log_file)
    prerequisite_checker: Callable[[Path], None] = lambda root: check_live_demo_prerequisites(root)
    calendar_preparer: Callable[[Path], None] = lambda root: prepare_live_calendars(root)


def check_live_demo_prerequisites(root: Path = PROJECT_ROOT) -> None:
    missing = []

    if not (root / TOKEN_PATH).exists():
        missing.append(
            "Google token is missing: run `python main.py google auth-url` "
            "and `python main.py google auth-finish ...` on this machine."
        )

    try:
        load_yandex_credentials(root)
    except RuntimeError:
        if not os.getenv("YANDEX_APP_PASSWORD"):
            missing.append(
                "YANDEX_APP_PASSWORD is missing: save the Yandex app password "
                "to local `.env` or an environment variable."
            )

    if missing:
        raise LiveDemoPrerequisiteError(" ".join(missing))


def prepare_live_calendars(root: Path = PROJECT_ROOT) -> None:
    google_service = build_calendar_service(root)
    create_google_sync_calendar(google_service, root=root)
    clear_google_sync_calendar(google_service, root=root)

    yandex_client = build_yandex_client(root)
    create_yandex_sync_calendar(yandex_client, root=root)
    clear_yandex_sync_calendar(yandex_client, root=root)


def build_live_calendar_links(root: Path = PROJECT_ROOT) -> LiveCalendarLinks:
    missing = []
    google_config = None
    yandex_config = None

    try:
        google_config = load_google_sync_calendar_config(root)
    except FileNotFoundError:
        missing.append(
            "Google sync calendar config is missing: run "
            "`python main.py live-links --prepare` first."
        )

    try:
        yandex_config = load_yandex_sync_calendar_config(root)
    except FileNotFoundError:
        missing.append(
            "Yandex sync calendar config is missing: run "
            "`python main.py live-links --prepare` first."
        )

    if missing:
        raise LiveLinksError(" ".join(missing))

    assert google_config is not None
    assert yandex_config is not None
    return LiveCalendarLinks(
        google_url=(
            "https://calendar.google.com/calendar/u/0/r?"
            f"cid={quote(google_config.calendar_id, safe='')}"
        ),
        yandex_url="https://calendar.yandex.ru/",
        yandex_calendar_name=yandex_config.name,
        json_paths=tuple(
            root / "data" / "output" / account.filename
            for account in CALENDAR_ACCOUNTS
        ),
    )


def print_live_links(
    root: Path = PROJECT_ROOT,
    *,
    prepare: bool = False,
    prerequisite_checker: Callable[[Path], None] = check_live_demo_prerequisites,
    calendar_preparer: Callable[[Path], None] = prepare_live_calendars,
) -> LiveCalendarLinks:
    try:
        prerequisite_checker(root)
        if prepare:
            print("Preparing clean Google and Yandex test calendars...")
            calendar_preparer(root)
        links = build_live_calendar_links(root)
    except LiveDemoError:
        raise
    except Exception as exc:
        raise LiveLinksError(str(exc)) from exc

    print("LIVE CALENDAR LINKS")
    print(f"- Google test calendar: {links.google_url}")
    print(
        "- Yandex Calendar: "
        f"{links.yandex_url} (calendar: {links.yandex_calendar_name})"
    )
    print("- Local JSON calendars:")
    for path in links.json_paths:
        print(f"  - {path}")

    print("\nManual check:")
    print("1. Open the Google test calendar link.")
    print("2. Create any event in that Google test calendar.")
    print("3. Run: python main.py sync --real-google --real-yandex")
    print("4. Open Yandex Calendar and find the copied event.")
    print("5. Create an event in the Yandex test calendar.")
    print("6. Run: python main.py sync --real-google --real-yandex")
    print("7. Open Google Calendar and find the copied event.")
    return links


def configure_live_demo_logger(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("calendar_sync_live_demo")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


class VisualGuide:
    def __init__(
        self,
        *,
        enabled: bool,
        pause_callback: Callable[[str], None],
    ) -> None:
        self.enabled = enabled
        self.pause_callback = pause_callback
        self.links_printed = False

    def show_links_once(self, root: Path) -> None:
        if not self.enabled or self.links_printed:
            return
        links = build_live_calendar_links(root)
        print("\nOpen these calendars to watch the visual demo:")
        print(f"- Google test calendar: {links.google_url}")
        print(
            "- Yandex Calendar: "
            f"{links.yandex_url} (calendar: {links.yandex_calendar_name})"
        )
        print("- Local JSON calendars:")
        for path in links.json_paths:
            print(f"  - {path}")
        self.links_printed = True
        self.pause("Open the calendar links, then press Enter to start the demo.")

    def pause(self, message: str) -> None:
        if self.enabled:
            self.pause_callback(message)


def default_visual_pause(message: str) -> None:
    input(f"\n{message}\nPress Enter to continue...")


def run_live_demo(
    root: Path = PROJECT_ROOT,
    *,
    dependencies: LiveDemoDependencies | None = None,
    visual: bool = False,
    pause_callback: Callable[[str], None] | None = None,
) -> LiveDemoResult:
    deps = dependencies or LiveDemoDependencies()
    ensure_project_dirs(root)
    visual_guide = VisualGuide(
        enabled=visual,
        pause_callback=pause_callback or default_visual_pause,
    )

    try:
        deps.prerequisite_checker(root)
        logger = deps.logger_factory(root / "logs" / "sync.log")
        database = deps.database_builder(root)

        print("Live demo setup: preparing clean JSON, Google, and Yandex calendars")

        _run_json_to_live_scenario(root, deps, database, logger, visual_guide)
        _run_google_to_all_scenario(root, deps, database, logger, visual_guide)
        _run_yandex_to_all_scenario(root, deps, database, logger, visual_guide)

    except LiveDemoError:
        raise
    except Exception as exc:
        raise LiveDemoError(str(exc)) from exc

    lines = (
        "LIVE DEMO PASSED",
        "- Google Calendar: create/update/delete OK",
        "- Yandex Calendar: create/update/delete OK",
        "- Google <-> Yandex sync OK",
        "- Duplicate protection OK",
    )
    for line in lines:
        print(line)
    return LiveDemoResult(lines=lines)


def _run_json_to_live_scenario(
    root: Path,
    deps: LiveDemoDependencies,
    database: Database,
    logger: logging.Logger,
    visual: VisualGuide,
) -> None:
    print("\nScenario 1: Outlook JSON -> Google + Yandex")
    adapters = _reset_and_build_adapters(root, deps, database)
    visual.show_links_once(root)
    manager = _find_adapter(adapters, owner="manager", system="outlook")
    google = _find_adapter(adapters, owner="developer_2", system="google")
    yandex = _find_adapter(adapters, owner="developer_1", system="yandex")
    leader = _find_adapter(adapters, owner="leader", system="yandex")

    manager.create_event(
        _event(
            event_id="live_demo_outlook_1",
            title="Live Demo Outlook to Google and Yandex",
            description="Created in Outlook JSON calendar",
            organizer="manager",
            source_system="outlook",
            source_owner="manager",
            start=datetime(2026, 7, 1, 10, 0, 0),
            end=datetime(2026, 7, 1, 11, 0, 0),
            updated_at=datetime(2026, 7, 1, 9, 0, 0),
        )
    )
    _sync(adapters, database, logger)
    _assert_confirmed(google, "Live Demo Outlook to Google and Yandex")
    _assert_confirmed(yandex, "Live Demo Outlook to Google and Yandex")
    _assert_confirmed(leader, "Live Demo Outlook to Google and Yandex")
    print("- created Google and Yandex copies from Outlook JSON")
    visual.pause(
        "Check Google and Yandex: event "
        "'Live Demo Outlook to Google and Yandex' should be visible."
    )

    _update_event_title(
        manager,
        "Live Demo Outlook to Google and Yandex",
        "Live Demo Outlook Updated",
        datetime(2026, 7, 1, 9, 30, 0),
    )
    _sync(adapters, database, logger)
    _assert_confirmed(google, "Live Demo Outlook Updated")
    _assert_confirmed(yandex, "Live Demo Outlook Updated")
    _assert_confirmed(leader, "Live Demo Outlook Updated")
    print("- propagated Outlook JSON update")
    visual.pause(
        "Check Google and Yandex: the event title should now be "
        "'Live Demo Outlook Updated'."
    )

    _mark_deleted(manager, "Live Demo Outlook Updated", datetime(2026, 7, 1, 10, 0, 0))
    _sync(adapters, database, logger)
    _assert_deleted(google, "Live Demo Outlook Updated")
    _assert_deleted(yandex, "Live Demo Outlook Updated")
    _assert_deleted(leader, "Live Demo Outlook Updated")
    print("- propagated Outlook JSON deletion")
    visual.pause(
        "Check Google and Yandex: the event should be deleted or marked cancelled."
    )


def _run_google_to_all_scenario(
    root: Path,
    deps: LiveDemoDependencies,
    database: Database,
    logger: logging.Logger,
    visual: VisualGuide,
) -> None:
    print("\nScenario 2: Google -> Yandex + JSON")
    adapters = _reset_and_build_adapters(root, deps, database)
    google = _find_adapter(adapters, owner="developer_2", system="google")
    yandex = _find_adapter(adapters, owner="developer_1", system="yandex")
    manager = _find_adapter(adapters, owner="manager", system="outlook")
    leader = _find_adapter(adapters, owner="leader", system="yandex")

    created = google.create_event(
        _event(
            event_id="",
            title="Live Demo Google to Everyone",
            description="Created in Google test calendar",
            organizer="developer_2",
            source_system="google",
            source_owner="developer_2",
            start=datetime(2026, 7, 2, 10, 0, 0),
            end=datetime(2026, 7, 2, 11, 0, 0),
            updated_at=datetime(2026, 7, 2, 9, 0, 0),
        )
    )
    _sync(adapters, database, logger)
    _assert_confirmed(yandex, "Live Demo Google to Everyone")
    _assert_confirmed(manager, "Live Demo Google to Everyone")
    _assert_confirmed(leader, "Live Demo Google to Everyone")

    _sync(adapters, database, logger)
    _assert_single_confirmed_event(adapters, "Live Demo Google to Everyone")
    print("- created Yandex and JSON copies without duplicates")
    visual.pause(
        "Check Yandex and JSON files: event "
        "'Live Demo Google to Everyone' should be copied from Google."
    )

    current = _find_event_by_id(google, created.id)
    google.update_event(
        current.id,
        current.model_copy(
            update={
                "title": "Live Demo Google Updated",
                "updated_at": datetime(2026, 7, 2, 9, 30, 0),
            }
        ),
    )
    _sync(adapters, database, logger)
    _assert_confirmed(yandex, "Live Demo Google Updated")
    _assert_confirmed(manager, "Live Demo Google Updated")
    _assert_confirmed(leader, "Live Demo Google Updated")
    print("- propagated Google update")
    visual.pause(
        "Check Yandex and JSON files: the Google event should now be "
        "'Live Demo Google Updated'."
    )

    google.delete_event(created.id)
    _sync(adapters, database, logger)
    _assert_deleted(yandex, "Live Demo Google Updated")
    _assert_deleted(manager, "Live Demo Google Updated")
    _assert_deleted(leader, "Live Demo Google Updated")
    print("- propagated Google deletion")
    visual.pause(
        "Check Yandex and JSON files: the Google-origin event should be deleted."
    )


def _run_yandex_to_all_scenario(
    root: Path,
    deps: LiveDemoDependencies,
    database: Database,
    logger: logging.Logger,
    visual: VisualGuide,
) -> None:
    print("\nScenario 3: Yandex -> Google + JSON")
    adapters = _reset_and_build_adapters(root, deps, database)
    yandex = _find_adapter(adapters, owner="developer_1", system="yandex")
    google = _find_adapter(adapters, owner="developer_2", system="google")
    manager = _find_adapter(adapters, owner="manager", system="outlook")
    leader = _find_adapter(adapters, owner="leader", system="yandex")

    created = yandex.create_event(
        _event(
            event_id="",
            title="Live Demo Yandex to Everyone",
            description="Created in Yandex test calendar",
            organizer="developer_1",
            source_system="yandex",
            source_owner="developer_1",
            start=datetime(2026, 7, 3, 10, 0, 0),
            end=datetime(2026, 7, 3, 11, 0, 0),
            updated_at=datetime(2026, 7, 3, 9, 0, 0),
        )
    )
    _sync(adapters, database, logger)
    _assert_confirmed(google, "Live Demo Yandex to Everyone")
    _assert_confirmed(manager, "Live Demo Yandex to Everyone")
    _assert_confirmed(leader, "Live Demo Yandex to Everyone")

    _sync(adapters, database, logger)
    _assert_single_confirmed_event(adapters, "Live Demo Yandex to Everyone")
    print("- created Google and JSON copies without duplicates")
    visual.pause(
        "Check Google and JSON files: event "
        "'Live Demo Yandex to Everyone' should be copied from Yandex."
    )

    current = _find_event_by_id(yandex, created.id)
    yandex.update_event(
        current.id,
        current.model_copy(
            update={
                "title": "Live Demo Yandex Updated",
                "updated_at": datetime(2026, 7, 3, 9, 30, 0),
            }
        ),
    )
    _sync(adapters, database, logger)
    _assert_confirmed(google, "Live Demo Yandex Updated")
    _assert_confirmed(manager, "Live Demo Yandex Updated")
    _assert_confirmed(leader, "Live Demo Yandex Updated")
    print("- propagated Yandex update")
    visual.pause(
        "Check Google and JSON files: the Yandex event should now be "
        "'Live Demo Yandex Updated'."
    )

    yandex.delete_event(created.id)
    _sync(adapters, database, logger)
    _assert_deleted(google, "Live Demo Yandex Updated")
    _assert_deleted(manager, "Live Demo Yandex Updated")
    _assert_deleted(leader, "Live Demo Yandex Updated")
    print("- propagated Yandex deletion")
    visual.pause(
        "Check Google and JSON files: the Yandex-origin event should be deleted."
    )


def _reset_and_build_adapters(
    root: Path,
    deps: LiveDemoDependencies,
    database: Database,
) -> list[CalendarAdapter]:
    database.reset_db()
    _reset_json_output(root)
    deps.calendar_preparer(root)
    return deps.adapter_builder(
        root=root,
        use_real_google=True,
        use_real_yandex=True,
    )


def _reset_json_output(root: Path) -> None:
    for account in CALENDAR_ACCOUNTS:
        path = root / "data" / "output" / account.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]", encoding="utf-8")


def _sync(
    adapters: list[CalendarAdapter],
    database: Database,
    logger: logging.Logger,
) -> None:
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


def _event(
    *,
    event_id: str,
    title: str,
    description: str,
    organizer: str,
    source_system: str,
    source_owner: str,
    start: datetime,
    end: datetime,
    updated_at: datetime,
) -> CalendarEvent:
    return CalendarEvent(
        id=event_id,
        title=title,
        description=description,
        start_time=start,
        end_time=end,
        organizer=organizer,
        attendees=["developer_1", "developer_2", "manager", "leader"],
        source_system=source_system,
        source_owner=source_owner,
        status="confirmed",
        updated_at=updated_at,
    )


def _find_adapter(
    adapters: list[CalendarAdapter],
    *,
    owner: str,
    system: str,
) -> CalendarAdapter:
    for adapter in adapters:
        if adapter.owner == owner and adapter.system == system:
            return adapter
    raise LiveDemoError(f"Adapter {system}/{owner} not found")


def _find_event_by_id(adapter: CalendarAdapter, event_id: str) -> CalendarEvent:
    for event in adapter.get_events():
        if event.id == event_id:
            return event
    raise LiveDemoError(f"Event id {event_id!r} not found in {adapter.system}/{adapter.owner}")


def _find_event_by_title(adapter: CalendarAdapter, title: str) -> CalendarEvent:
    matches = [event for event in adapter.get_events() if event.title == title]
    if len(matches) != 1:
        raise LiveDemoError(
            f"Expected exactly one event {title!r} in "
            f"{adapter.system}/{adapter.owner}, found {len(matches)}"
        )
    return matches[0]


def _update_event_title(
    adapter: CalendarAdapter,
    old_title: str,
    new_title: str,
    updated_at: datetime,
) -> None:
    event = _find_event_by_title(adapter, old_title)
    adapter.update_event(
        event.id,
        event.model_copy(update={"title": new_title, "updated_at": updated_at}),
    )


def _mark_deleted(
    adapter: CalendarAdapter,
    title: str,
    updated_at: datetime,
) -> None:
    event = _find_event_by_title(adapter, title)
    adapter.update_event(
        event.id,
        event.model_copy(update={"status": "deleted", "updated_at": updated_at}),
    )


def _assert_confirmed(adapter: CalendarAdapter, title: str) -> None:
    matches = [
        event
        for event in adapter.get_events()
        if event.title == title and event.status == "confirmed"
    ]
    if len(matches) != 1:
        raise LiveDemoError(
            f"Expected one confirmed event {title!r} in "
            f"{adapter.system}/{adapter.owner}, found {len(matches)}"
        )


def _assert_deleted(adapter: CalendarAdapter, title: str) -> None:
    matches = [
        event
        for event in adapter.get_events()
        if event.title == title and event.status == "deleted"
    ]
    if len(matches) != 1:
        raise LiveDemoError(
            f"Expected one deleted event {title!r} in "
            f"{adapter.system}/{adapter.owner}, found {len(matches)}"
        )


def _assert_single_confirmed_event(
    adapters: list[CalendarAdapter],
    title: str,
) -> None:
    for adapter in adapters:
        matches = [
            event
            for event in adapter.get_events()
            if event.title == title and event.status == "confirmed"
        ]
        if len(matches) != 1:
            raise LiveDemoError(
                f"Duplicate check failed for {adapter.system}/{adapter.owner}: "
                f"expected 1 confirmed {title!r}, found {len(matches)}"
            )
