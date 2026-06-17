import logging
from datetime import datetime

from app.adapters import YandexCalendarAdapter
from app.bootstrap import build_sync_adapters
from app.config import CALENDAR_ACCOUNTS
from app.models import CalendarEvent
from app.services.sync_service import SyncService
from app.services.yandex_calendar_config import (
    YandexCalendarConfig,
    create_sync_calendar,
    save_sync_calendar_config,
)
from app.storage import Database


def test_create_yandex_sync_calendar_saves_config(tmp_path):
    client = FakeCalDAVClient()

    result = create_sync_calendar(client, root=tmp_path, name="Yandex Test")

    assert result.created is True
    assert result.config.name == "Yandex Test"
    assert result.config.calendar_url == "https://caldav.example/yandex-test/"
    assert (tmp_path / "data" / "yandex_calendar_config.json").exists()


def test_build_sync_adapters_replaces_developer_1_yandex(tmp_path, monkeypatch):
    calendar = FakeCalDAVCalendar()
    save_sync_calendar_config(
        YandexCalendarConfig(calendar_url="https://caldav.example/test/", name="Test"),
        tmp_path,
    )
    monkeypatch.setattr("app.bootstrap.build_yandex_client", lambda root: object())
    monkeypatch.setattr(
        "app.bootstrap.load_yandex_sync_calendar",
        lambda client, root: calendar,
    )

    adapters = build_sync_adapters(root=tmp_path, use_real_yandex=True)

    assert any(isinstance(adapter, YandexCalendarAdapter) for adapter in adapters)
    assert len(adapters) == len(CALENDAR_ACCOUNTS)
    assert not any(
        adapter.owner == "developer_1"
        and adapter.system == "yandex"
        and not isinstance(adapter, YandexCalendarAdapter)
        for adapter in adapters
    )


def test_real_yandex_sync_creates_yandex_copy_with_fake_calendar(
    tmp_path,
    monkeypatch,
):
    calendar = FakeCalDAVCalendar()
    save_sync_calendar_config(
        YandexCalendarConfig(calendar_url="https://caldav.example/test/", name="Test"),
        tmp_path,
    )
    monkeypatch.setattr("app.bootstrap.build_yandex_client", lambda root: object())
    monkeypatch.setattr(
        "app.bootstrap.load_yandex_sync_calendar",
        lambda client, root: calendar,
    )
    adapters = build_sync_adapters(root=tmp_path, use_real_yandex=True)
    manager = find_adapter(adapters, owner="manager", system="outlook")
    manager.create_event(
        CalendarEvent(
            id="outlook_event_1",
            title="Manager event",
            description="From JSON",
            start_time=datetime(2026, 6, 22, 10, 0, 0),
            end_time=datetime(2026, 6, 22, 11, 0, 0),
            organizer="manager",
            attendees=["developer_1", "developer_2", "leader"],
            source_system="outlook",
            source_owner="manager",
            status="confirmed",
            updated_at=datetime(2026, 6, 22, 9, 0, 0),
        )
    )

    result = SyncService(
        adapters=adapters,
        database=Database(tmp_path / "sync.db"),
        logger=logging.getLogger("yandex_live_sync_test"),
    ).sync()

    yandex = find_adapter(adapters, owner="developer_1", system="yandex")
    assert result.events_created == 3
    assert [event.title for event in yandex.get_events()] == ["Manager event"]


def find_adapter(adapters, *, owner: str, system: str):
    for adapter in adapters:
        if adapter.owner == owner and adapter.system == system:
            return adapter
    raise LookupError(f"Adapter {system}/{owner} not found")


class FakeCalDAVClient:
    def __init__(self):
        self.principal_resource = FakePrincipal()

    def principal(self):
        return self.principal_resource


class FakePrincipal:
    def __init__(self):
        self.calendar_items = []

    def calendars(self):
        return self.calendar_items

    def make_calendar(self, name):
        calendar = FakeCalendarInfo(
            name=name,
            url=f"https://caldav.example/{name.lower().replace(' ', '-')}/",
        )
        self.calendar_items.append(calendar)
        return calendar


class FakeCalendarInfo:
    def __init__(self, *, name, url):
        self.name = name
        self.url = url


class FakeCalDAVCalendar:
    def __init__(self):
        self.items = {}

    def events(self):
        return list(self.items.values())

    def save_event(self, ical, no_overwrite=False):
        resource = FakeCalDAVEvent(ical, self)
        uid = resource.uid
        if no_overwrite and uid in self.items:
            raise RuntimeError(f"Event {uid} already exists")
        self.items[uid] = resource
        return resource

    def event_by_uid(self, uid):
        return self.items[uid]


class FakeCalDAVEvent:
    def __init__(self, data, calendar):
        self.data = data
        self.calendar = calendar

    @property
    def uid(self):
        for line in self.data.splitlines():
            if line.startswith("UID:"):
                return line.removeprefix("UID:")
        raise ValueError("UID not found")

    def save(self, no_create=False):
        self.calendar.items[self.uid] = self
        return self

    def delete(self):
        self.calendar.items.pop(self.uid, None)
