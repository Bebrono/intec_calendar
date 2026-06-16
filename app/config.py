from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CalendarAccount:
    owner: str
    system: str
    filename: str
    display_name: str


CALENDAR_ACCOUNTS = (
    CalendarAccount(
        owner="developer_1",
        system="yandex",
        filename="yandex_developer_1.json",
        display_name="Разработчик 1",
    ),
    CalendarAccount(
        owner="developer_2",
        system="google",
        filename="google_developer_2.json",
        display_name="Разработчик 2",
    ),
    CalendarAccount(
        owner="manager",
        system="outlook",
        filename="outlook_manager.json",
        display_name="Менеджер",
    ),
    CalendarAccount(
        owner="leader",
        system="yandex",
        filename="yandex_leader.json",
        display_name="Руководитель",
    ),
)


def ensure_project_dirs(root: Path = PROJECT_ROOT) -> None:
    for relative in ("data/input", "data/output", "logs"):
        (root / relative).mkdir(parents=True, exist_ok=True)
