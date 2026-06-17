from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import PROJECT_ROOT, ensure_project_dirs
from app.services.google_event_mapper import DEFAULT_TIMEZONE
from googleapiclient.errors import HttpError


CONFIG_PATH = Path("data/google_calendar_config.json")
DEFAULT_SYNC_CALENDAR_SUMMARY = "Calendar Sync Service Test"


@dataclass(frozen=True)
class GoogleCalendarConfig:
    calendar_id: str
    summary: str


@dataclass(frozen=True)
class GoogleCalendarCreationResult:
    config: GoogleCalendarConfig
    created: bool


def recreate_sync_calendar(
    service,
    *,
    root: Path = PROJECT_ROOT,
    summary: str = DEFAULT_SYNC_CALENDAR_SUMMARY,
) -> GoogleCalendarCreationResult:
    existing = load_sync_calendar_config(root, required=False)
    if existing is not None:
        try:
            service.calendars().delete(calendarId=existing.calendar_id).execute()
        except HttpError as exc:
            if exc.resp.status not in (404, 410):
                raise
        (root / CONFIG_PATH).unlink(missing_ok=True)

    return create_sync_calendar(service, root=root, summary=summary)


def create_sync_calendar(
    service,
    *,
    root: Path = PROJECT_ROOT,
    summary: str = DEFAULT_SYNC_CALENDAR_SUMMARY,
) -> GoogleCalendarCreationResult:
    existing = load_sync_calendar_config(root, required=False)
    if existing is not None:
        return GoogleCalendarCreationResult(config=existing, created=False)

    payload = (
        service.calendars()
        .insert(body={"summary": summary, "timeZone": DEFAULT_TIMEZONE})
        .execute()
    )
    config = GoogleCalendarConfig(
        calendar_id=payload["id"],
        summary=payload.get("summary") or summary,
    )
    save_sync_calendar_config(config, root)
    return GoogleCalendarCreationResult(config=config, created=True)


def clear_sync_calendar(service, *, root: Path = PROJECT_ROOT) -> int:
    config = load_sync_calendar_config(root)
    deleted_count = 0
    request = service.events().list(
        calendarId=config.calendar_id,
        maxResults=2500,
        singleEvents=True,
        showDeleted=True,
    )
    while request is not None:
        response = request.execute()
        for item in response.get("items", []):
            if item.get("id"):
                try:
                    service.events().delete(
                        calendarId=config.calendar_id,
                        eventId=item["id"],
                    ).execute()
                    deleted_count += 1
                except HttpError as exc:
                    if exc.resp.status not in (404, 410):
                        raise
        request = service.events().list_next(request, response)
    return deleted_count


def load_sync_calendar_config(
    root: Path = PROJECT_ROOT,
    *,
    required: bool = True,
) -> GoogleCalendarConfig | None:
    path = root / CONFIG_PATH
    if not path.exists():
        if required:
            raise FileNotFoundError(
                "Google sync calendar config not found. "
                "Run `python main.py google create-sync-calendar` first."
            )
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    return GoogleCalendarConfig(
        calendar_id=data["calendar_id"],
        summary=data["summary"],
    )


def save_sync_calendar_config(
    config: GoogleCalendarConfig,
    root: Path = PROJECT_ROOT,
) -> Path:
    ensure_project_dirs(root)
    path = root / CONFIG_PATH
    path.write_text(
        json.dumps(
            {"calendar_id": config.calendar_id, "summary": config.summary},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
