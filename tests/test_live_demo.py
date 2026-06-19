from __future__ import annotations

from app.bootstrap import build_sync_adapters
from app.services.google_calendar_config import (
    GoogleCalendarConfig,
    save_sync_calendar_config as save_google_sync_calendar_config,
)
from app.services.live_demo import (
    LiveDemoDependencies,
    LiveDemoPrerequisiteError,
    LiveLinksError,
    check_live_demo_prerequisites,
    print_live_links,
    run_live_demo,
)
from app.services.yandex_calendar_config import (
    YANDEX_SYNC_OWNERS,
    YandexCalendarConfig,
    save_sync_calendar_config as save_yandex_sync_calendar_config,
)


def test_live_demo_runs_google_and_yandex_scenarios(tmp_path, monkeypatch, capsys):
    dependencies, adapter_flags = _fake_live_dependencies(monkeypatch)

    result = run_live_demo(
        tmp_path,
        dependencies=dependencies,
    )

    output = capsys.readouterr().out
    assert result.lines[0] == "LIVE DEMO PASSED"
    assert "Google Calendar: create/update/delete OK" in output
    assert "Yandex Calendar: create/update/delete OK" in output
    assert "Google <-> Yandex sync OK" in output
    assert "Duplicate protection OK" in output
    assert adapter_flags
    assert all(flags == (True, True) for flags in adapter_flags)


def test_live_demo_visual_mode_prints_links_and_pauses(
    tmp_path,
    monkeypatch,
    capsys,
):
    dependencies, _ = _fake_live_dependencies(monkeypatch)
    pauses = []

    run_live_demo(
        tmp_path,
        dependencies=dependencies,
        visual=True,
        pause_callback=pauses.append,
    )

    output = capsys.readouterr().out
    assert "Open these calendars to watch the visual demo" in output
    assert "Google test calendar:" in output
    assert "Yandex Calendar:" in output
    assert len(pauses) == 10
    assert pauses[0] == "Open the calendar links, then press Enter to start the demo."
    assert any("Live Demo Google to Everyone" in pause for pause in pauses)
    assert any("Live Demo Yandex Updated" in pause for pause in pauses)


def test_live_demo_prerequisite_error_is_short_and_actionable(tmp_path, monkeypatch):
    monkeypatch.delenv("YANDEX_APP_PASSWORD", raising=False)

    try:
        check_live_demo_prerequisites(tmp_path)
    except LiveDemoPrerequisiteError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected LiveDemoPrerequisiteError")

    assert "Google token is missing" in message
    assert "YANDEX_APP_PASSWORD is missing" in message
    assert "YANDEX_LEADER_APP_PASSWORD is missing" in message
    assert "Traceback" not in message


def test_live_links_prints_calendar_urls(tmp_path, capsys):
    save_google_sync_calendar_config(
        GoogleCalendarConfig(
            calendar_id="calendar_id@example.com",
            summary="Test Google",
        ),
        tmp_path,
    )
    save_yandex_sync_calendar_config(
        YandexCalendarConfig(
            calendar_url="https://caldav.example/test/",
            name="Test Yandex",
        ),
        tmp_path,
    )
    save_yandex_sync_calendar_config(
        YandexCalendarConfig(
            calendar_url="https://caldav.example/leader/",
            name="Test Yandex Leader",
        ),
        tmp_path,
        owner="leader",
    )

    links = print_live_links(
        tmp_path,
        prerequisite_checker=lambda root: None,
    )

    output = capsys.readouterr().out
    assert links.google_url.endswith("cid=calendar_id%40example.com")
    assert "LIVE CALENDAR LINKS" in output
    assert "https://calendar.google.com/calendar/u/0/r?cid=calendar_id%40example.com" in output
    assert "Yandex Calendar (developer_1): https://calendar.yandex.ru/ (calendar: Test Yandex)" in output
    assert "Yandex Calendar (leader): https://calendar.yandex.ru/ (calendar: Test Yandex Leader)" in output
    assert len(links.yandex_calendars) == 2
    assert str(tmp_path / "data" / "output" / "outlook_manager.json") in output
    assert "python main.py watch" in output
    assert "python main.py sync --real-google --real-yandex" not in output


def test_live_links_prepare_invokes_calendar_preparer(tmp_path, capsys):
    prepared_roots = []

    def prepare(root):
        prepared_roots.append(root)
        save_google_sync_calendar_config(
            GoogleCalendarConfig(calendar_id="calendar_1", summary="Test Google"),
            root,
        )
        save_yandex_sync_calendar_config(
            YandexCalendarConfig(
                calendar_url="https://caldav.example/test/",
                name="Test Yandex",
            ),
            root,
        )
        save_yandex_sync_calendar_config(
            YandexCalendarConfig(
                calendar_url="https://caldav.example/leader/",
                name="Test Yandex Leader",
            ),
            root,
            owner="leader",
        )

    print_live_links(
        tmp_path,
        prepare=True,
        prerequisite_checker=lambda root: None,
        calendar_preparer=prepare,
    )

    output = capsys.readouterr().out
    assert prepared_roots == [tmp_path]
    assert "Preparing clean Google and Yandex test calendars..." in output
    assert "LIVE CALENDAR LINKS" in output


def test_live_links_missing_config_is_short_and_actionable(tmp_path):
    try:
        print_live_links(
            tmp_path,
            prerequisite_checker=lambda root: None,
        )
    except LiveLinksError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected LiveLinksError")

    assert "Google sync calendar config is missing" in message
    assert "Yandex sync calendar config for developer_1 is missing" in message
    assert "Yandex sync calendar config for leader is missing" in message
    assert "Traceback" not in message


def _fake_live_dependencies(monkeypatch):
    google_service = FakeGoogleService()
    yandex_calendars = {owner: FakeCalDAVCalendar() for owner in YANDEX_SYNC_OWNERS}
    adapter_flags = []

    monkeypatch.setattr(
        "app.bootstrap.build_calendar_service",
        lambda root: google_service,
    )
    monkeypatch.setattr("app.bootstrap.build_yandex_client", lambda root, owner: owner)
    monkeypatch.setattr(
        "app.bootstrap.load_yandex_sync_calendar",
        lambda client, root, owner: yandex_calendars[owner],
    )

    def prepare_calendars(root):
        google_service.events_resource.items.clear()
        for calendar in yandex_calendars.values():
            calendar.items.clear()
        save_google_sync_calendar_config(
            GoogleCalendarConfig(calendar_id="calendar_1", summary="Test Google"),
            root,
        )
        for owner in YANDEX_SYNC_OWNERS:
            save_yandex_sync_calendar_config(
                YandexCalendarConfig(
                    calendar_url=f"https://caldav.example/{owner}/",
                    name=f"Test Yandex {owner}",
                ),
                root,
                owner=owner,
            )

    def adapter_builder(**kwargs):
        adapter_flags.append(
            (kwargs["use_real_google"], kwargs["use_real_yandex"])
        )
        return build_sync_adapters(**kwargs)

    return (
        LiveDemoDependencies(
            adapter_builder=adapter_builder,
            prerequisite_checker=lambda root: None,
            calendar_preparer=prepare_calendars,
        ),
        adapter_flags,
    )


class FakeGoogleService:
    def __init__(self):
        self.events_resource = FakeEventsResource()

    def events(self):
        return self.events_resource


class FakeEventsResource:
    def __init__(self):
        self.items = {}
        self.counter = 0

    def list(self, **kwargs):
        return FakeRequest({"items": list(self.items.values())})

    def list_next(self, request, response):
        return None

    def insert(self, *, calendarId, body):
        self.counter += 1
        event_id = f"google_event_{self.counter}"
        payload = self._with_google_fields(event_id, body)
        self.items[event_id] = payload
        return FakeRequest(payload)

    def update(self, *, calendarId, eventId, body):
        payload = self._with_google_fields(eventId, body)
        self.items[eventId] = payload
        return FakeRequest(payload)

    def get(self, *, calendarId, eventId):
        return FakeRequest(self.items[eventId])

    def delete(self, *, calendarId, eventId):
        self.items.pop(eventId, None)
        return FakeRequest({})

    def _with_google_fields(self, event_id, body):
        payload = dict(body)
        updated = (
            "2026-07-04T09:00:00Z"
            if body.get("status") == "cancelled"
            else "2026-07-01T09:00:00Z"
        )
        payload.update(
            {
                "id": event_id,
                "updated": updated,
                "creator": {"email": "owner@example.com"},
                "organizer": {"email": "owner@example.com"},
                "eventType": "default",
            }
        )
        return payload


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


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
