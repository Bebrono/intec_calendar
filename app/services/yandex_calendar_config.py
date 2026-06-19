from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from caldav import Calendar, DAVClient
from dotenv import dotenv_values

from app.config import PROJECT_ROOT, ensure_project_dirs


DEFAULT_YANDEX_OWNER = "developer_1"
YANDEX_SYNC_OWNERS = ("developer_1", "leader")
CONFIG_PATHS = {
    "developer_1": Path("data/yandex_calendar_config.json"),
    "leader": Path("data/yandex_leader_calendar_config.json"),
}
DEFAULT_CALDAV_URL = "https://caldav.yandex.ru/"
DEFAULT_USERNAMES = {
    "developer_1": "Bebrono@yandex.ru",
    "leader": "siskosardelkin@yandex.ru",
}
DEFAULT_SYNC_CALENDAR_NAMES = {
    "developer_1": "Calendar Sync Service Yandex Test",
    "leader": "Calendar Sync Service Yandex Leader Test",
}
LEGACY_SYNC_CALENDAR_NAMES = {
    "developer_1": ("Calendar Sync Service Yandex Developer Test",),
    "leader": (),
}


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


@dataclass(frozen=True)
class YandexCalendarDeduplicationResult:
    config: YandexCalendarConfig
    deleted_count: int


def load_yandex_credentials(
    root: Path = PROJECT_ROOT,
    *,
    owner: str = DEFAULT_YANDEX_OWNER,
) -> YandexCredentials:
    owner = _validate_owner(owner)
    env_path = root / ".env"
    file_values = dotenv_values(env_path) if env_path.exists() else {}
    prefix = _env_prefix(owner)

    caldav_url = (
        os.getenv(f"{prefix}_CALDAV_URL")
        or file_values.get(f"{prefix}_CALDAV_URL")
        or os.getenv("YANDEX_CALDAV_URL")
        or file_values.get("YANDEX_CALDAV_URL")
        or DEFAULT_CALDAV_URL
    )
    username = (
        os.getenv(f"{prefix}_USERNAME")
        or file_values.get(f"{prefix}_USERNAME")
        or DEFAULT_USERNAMES[owner]
    )
    password_key = f"{prefix}_APP_PASSWORD"
    password = os.getenv(password_key) or file_values.get(password_key)
    if not password:
        raise RuntimeError(
            f"{password_key} is not configured. "
            "Create a Yandex app password and save it to local .env."
        )
    if not caldav_url.endswith("/"):
        caldav_url = f"{caldav_url}/"

    return YandexCredentials(
        caldav_url=caldav_url,
        username=username,
        password=password,
    )


def build_yandex_client(
    root: Path = PROJECT_ROOT,
    *,
    owner: str = DEFAULT_YANDEX_OWNER,
) -> DAVClient:
    credentials = load_yandex_credentials(root, owner=owner)
    return DAVClient(
        url=credentials.caldav_url,
        username=credentials.username,
        password=credentials.password,
    )


def create_sync_calendar(
    client: DAVClient,
    *,
    root: Path = PROJECT_ROOT,
    name: str | None = None,
    owner: str = DEFAULT_YANDEX_OWNER,
) -> YandexCalendarCreationResult:
    owner = _validate_owner(owner)
    calendar_name = name or DEFAULT_SYNC_CALENDAR_NAMES[owner]
    principal = client.principal()
    for calendar in principal.calendars():
        if getattr(calendar, "name", None) == calendar_name:
            config = YandexCalendarConfig(
                calendar_url=str(calendar.url),
                name=calendar_name,
            )
            save_sync_calendar_config(config, root, owner=owner)
            return YandexCalendarCreationResult(config=config, created=False)

    calendar = principal.make_calendar(name=calendar_name)
    for listed_calendar in principal.calendars():
        if getattr(listed_calendar, "name", None) == calendar_name:
            calendar = listed_calendar
            break
    config = YandexCalendarConfig(calendar_url=str(calendar.url), name=calendar_name)
    save_sync_calendar_config(config, root, owner=owner)
    return YandexCalendarCreationResult(config=config, created=True)


def deduplicate_sync_calendars(
    client: DAVClient,
    *,
    root: Path = PROJECT_ROOT,
    owner: str = DEFAULT_YANDEX_OWNER,
) -> YandexCalendarDeduplicationResult:
    owner = _validate_owner(owner)
    principal = client.principal()
    calendar_names = _sync_calendar_names(owner)
    calendars = [
        calendar
        for calendar in principal.calendars()
        if getattr(calendar, "name", None) in calendar_names
    ]

    if not calendars:
        created = create_sync_calendar(client, root=root, owner=owner)
        return YandexCalendarDeduplicationResult(
            config=created.config,
            deleted_count=0,
        )

    canonical_name = DEFAULT_SYNC_CALENDAR_NAMES[owner]
    configured = load_sync_calendar_config(root, owner=owner, required=False)
    keep = next(
        (
            calendar
            for calendar in calendars
            if getattr(calendar, "name", None) == canonical_name
        ),
        None,
    )
    if keep is None and configured is not None:
        keep = next(
            (
                calendar
                for calendar in calendars
                if str(calendar.url) == configured.calendar_url
            ),
            None,
        )
    keep = keep or calendars[0]

    deleted_count = 0
    for calendar in calendars:
        if str(calendar.url) == str(keep.url):
            continue
        _delete_calendar(calendar)
        deleted_count += 1

    config = YandexCalendarConfig(
        calendar_url=str(keep.url),
        name=str(getattr(keep, "name", canonical_name)),
    )
    save_sync_calendar_config(config, root, owner=owner)
    return YandexCalendarDeduplicationResult(
        config=config,
        deleted_count=deleted_count,
    )


def clear_sync_calendar(
    client: DAVClient,
    *,
    root: Path = PROJECT_ROOT,
    owner: str = DEFAULT_YANDEX_OWNER,
) -> int:
    calendar = load_sync_calendar(client, root=root, owner=owner)
    deleted_count = 0
    for event in calendar.events():
        event.delete()
        deleted_count += 1
    return deleted_count


def load_sync_calendar(
    client: DAVClient,
    *,
    root: Path = PROJECT_ROOT,
    owner: str = DEFAULT_YANDEX_OWNER,
) -> Calendar:
    config = load_sync_calendar_config(root, owner=owner)
    return Calendar(client=client, url=config.calendar_url)


def load_sync_calendar_config(
    root: Path = PROJECT_ROOT,
    *,
    owner: str = DEFAULT_YANDEX_OWNER,
    required: bool = True,
) -> YandexCalendarConfig | None:
    owner = _validate_owner(owner)
    path = root / CONFIG_PATHS[owner]
    if not path.exists():
        if required:
            raise FileNotFoundError(
                f"Yandex sync calendar config for {owner} not found. "
                f"Run `python main.py yandex --owner {owner} "
                "create-sync-calendar` first."
            )
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    return YandexCalendarConfig(calendar_url=data["calendar_url"], name=data["name"])


def save_sync_calendar_config(
    config: YandexCalendarConfig,
    root: Path = PROJECT_ROOT,
    *,
    owner: str = DEFAULT_YANDEX_OWNER,
) -> Path:
    owner = _validate_owner(owner)
    ensure_project_dirs(root)
    path = root / CONFIG_PATHS[owner]
    path.write_text(
        json.dumps(
            {"calendar_url": config.calendar_url, "name": config.name},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _env_prefix(owner: str) -> str:
    return "YANDEX" if owner == "developer_1" else f"YANDEX_{owner.upper()}"


def _sync_calendar_names(owner: str) -> tuple[str, ...]:
    return (
        DEFAULT_SYNC_CALENDAR_NAMES[owner],
        *LEGACY_SYNC_CALENDAR_NAMES[owner],
    )


def _delete_calendar(calendar) -> None:
    calendar.delete()


def _validate_owner(owner: str) -> str:
    if owner not in YANDEX_SYNC_OWNERS:
        allowed = ", ".join(YANDEX_SYNC_OWNERS)
        raise ValueError(f"Unsupported Yandex owner {owner!r}. Allowed: {allowed}.")
    return owner
