from __future__ import annotations

from pathlib import Path

from app.adapters import FileCalendarAdapter, GoogleCalendarAdapter, YandexCalendarAdapter
from app.config import CALENDAR_ACCOUNTS, PROJECT_ROOT, ensure_project_dirs
from app.services.event_mapper import EventMapper
from app.services.google_calendar_config import load_sync_calendar_config
from app.services.google_oauth import build_calendar_service
from app.services.yandex_calendar_config import (
    YANDEX_SYNC_OWNERS,
    build_yandex_client,
    load_sync_calendar as load_yandex_sync_calendar,
)
from app.storage import Database


def build_file_adapters(
    *,
    root: Path = PROJECT_ROOT,
    calendar_dir: str = "output",
    mapper: EventMapper | None = None,
) -> list[FileCalendarAdapter]:
    ensure_project_dirs(root)
    event_mapper = mapper or EventMapper()
    base_dir = root / "data" / calendar_dir
    return [
        FileCalendarAdapter(
            file_path=base_dir / account.filename,
            owner=account.owner,
            system=account.system,
            mapper=event_mapper,
        )
        for account in CALENDAR_ACCOUNTS
    ]


def build_sync_adapters(
    *,
    root: Path = PROJECT_ROOT,
    use_real_google: bool = False,
    use_real_yandex: bool = False,
    calendar_dir: str = "output",
    mapper: EventMapper | None = None,
) -> list:
    if not use_real_google and not use_real_yandex:
        return build_file_adapters(
            root=root,
            calendar_dir=calendar_dir,
            mapper=mapper,
        )

    ensure_project_dirs(root)
    event_mapper = mapper or EventMapper()
    base_dir = root / "data" / calendar_dir
    adapters = []
    for account in CALENDAR_ACCOUNTS:
        if account.owner == "developer_2" and account.system == "google":
            if use_real_google:
                continue
        if account.owner in YANDEX_SYNC_OWNERS and account.system == "yandex":
            if use_real_yandex:
                continue
        adapters.append(
            FileCalendarAdapter(
                file_path=base_dir / account.filename,
                owner=account.owner,
                system=account.system,
                mapper=event_mapper,
            )
        )

    if use_real_yandex:
        for owner in YANDEX_SYNC_OWNERS:
            yandex_client = build_yandex_client(root, owner=owner)
            adapters.append(
                YandexCalendarAdapter(
                    calendar=load_yandex_sync_calendar(
                        yandex_client,
                        root=root,
                        owner=owner,
                    ),
                    owner=owner,
                )
            )

    if use_real_google:
        google_config = load_sync_calendar_config(root)
        adapters.append(
            GoogleCalendarAdapter(
                service=build_calendar_service(root),
                owner="developer_2",
                calendar_id=google_config.calendar_id,
            )
        )
    return adapters


def build_database(root: Path = PROJECT_ROOT) -> Database:
    ensure_project_dirs(root)
    return Database(root / "data" / "sync.db")
