from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from caldav import Calendar, DAVClient
from dotenv import dotenv_values

from app.config import PROJECT_ROOT, ensure_project_dirs


CONFIG_PATH = Path("data/yandex_calendar_config.json")
DEFAULT_CALDAV_URL = "https://caldav.yandex.ru/"
DEFAULT_USERNAME = "Bebrono@yandex.ru"
DEFAULT_SYNC_CALENDAR_NAME = "Calendar Sync Service Yandex Test"


@dataclass(frozen=True)
class YandexCredentials:
    caldav_url: str
    username: str
    password: str


@dataclass(frozen=True)
class YandexCalendarConfig:
    calendar_url: str
    name: str


@dataclass(frozen=True)
class YandexCalendarCreationResult:
    config: YandexCalendarConfig
    created: bool


def load_yandex_credentials(root: Path = PROJECT_ROOT) -> YandexCredentials:
    env_path = root / ".env"
    file_values = dotenv_values(env_path) if env_path.exists() else {}

    caldav_url = (
        os.getenv("YANDEX_CALDAV_URL")
        or file_values.get("YANDEX_CALDAV_URL")
        or DEFAULT_CALDAV_URL
    )
    username = (
        os.getenv("YANDEX_USERNAME")
        or file_values.get("YANDEX_USERNAME")
        or DEFAULT_USERNAME
    )
    password = os.getenv("YANDEX_APP_PASSWORD") or file_values.get(
        "YANDEX_APP_PASSWORD"
    )
    if not password:
        raise RuntimeError(
            "YANDEX_APP_PASSWORD is not configured. "
            "Create a Yandex app password and save it to local .env."
        )
    if not caldav_url.endswith("/"):
        caldav_url = f"{caldav_url}/"

    return YandexCredentials(
        caldav_url=caldav_url,
        username=username,
        password=password,
    )


def build_yandex_client(root: Path = PROJECT_ROOT) -> DAVClient:
    credentials = load_yandex_credentials(root)
    return DAVClient(
        url=credentials.caldav_url,
        username=credentials.username,
        password=credentials.password,
    )


def create_sync_calendar(
    client: DAVClient,
    *,
    root: Path = PROJECT_ROOT,
    name: str = DEFAULT_SYNC_CALENDAR_NAME,
) -> YandexCalendarCreationResult:
    principal = client.principal()
    for calendar in principal.calendars():
        if getattr(calendar, "name", None) == name:
            config = YandexCalendarConfig(calendar_url=str(calendar.url), name=name)
            save_sync_calendar_config(config, root)
            return YandexCalendarCreationResult(config=config, created=False)

    calendar = principal.make_calendar(name=name)
    for listed_calendar in principal.calendars():
        if getattr(listed_calendar, "name", None) == name:
            calendar = listed_calendar
            break
    config = YandexCalendarConfig(calendar_url=str(calendar.url), name=name)
    save_sync_calendar_config(config, root)
    return YandexCalendarCreationResult(config=config, created=True)


def clear_sync_calendar(
    client: DAVClient,
    *,
    root: Path = PROJECT_ROOT,
) -> int:
    calendar = load_sync_calendar(client, root=root)
    deleted_count = 0
    for event in calendar.events():
        event.delete()
        deleted_count += 1
    return deleted_count


def load_sync_calendar(
    client: DAVClient,
    *,
    root: Path = PROJECT_ROOT,
) -> Calendar:
    config = load_sync_calendar_config(root)
    return Calendar(client=client, url=config.calendar_url)


def load_sync_calendar_config(
    root: Path = PROJECT_ROOT,
    *,
    required: bool = True,
) -> YandexCalendarConfig | None:
    path = root / CONFIG_PATH
    if not path.exists():
        if required:
            raise FileNotFoundError(
                "Yandex sync calendar config not found. "
                "Run `python main.py yandex create-sync-calendar` first."
            )
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    return YandexCalendarConfig(calendar_url=data["calendar_url"], name=data["name"])


def save_sync_calendar_config(
    config: YandexCalendarConfig,
    root: Path = PROJECT_ROOT,
) -> Path:
    ensure_project_dirs(root)
    path = root / CONFIG_PATH
    path.write_text(
        json.dumps(
            {"calendar_url": config.calendar_url, "name": config.name},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
