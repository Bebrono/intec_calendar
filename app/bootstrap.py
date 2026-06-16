from __future__ import annotations

from pathlib import Path

from app.adapters import FileCalendarAdapter
from app.config import CALENDAR_ACCOUNTS, PROJECT_ROOT, ensure_project_dirs
from app.services.event_mapper import EventMapper
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


def build_database(root: Path = PROJECT_ROOT) -> Database:
    ensure_project_dirs(root)
    return Database(root / "data" / "sync.db")
