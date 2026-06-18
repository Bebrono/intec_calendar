from __future__ import annotations

from app.bootstrap import build_sync_adapters
from app.services.google_calendar_config import (
    GoogleCalendarConfig,
    save_sync_calendar_config as save_google_sync_calendar_config,
)
from app.services.live_demo import (
    LiveDemoDependencies,
    LiveDemoPrerequisiteError,
    check_live_demo_prerequisites,
    run_live_demo,
)
from app.services.yandex_calendar_config import (
    YandexCalendarConfig,
    save_sync_calendar_config as save_yandex_sync_calendar_config,
)


def test_live_demo_runs_google_and_yandex_scenarios(tmp_path, monkeypatch, capsys):
    google_service = FakeGoogleService()
    yandex_calendar = FakeCalDAVCalendar()
    adapter_flags = []

    monkeypatch.setattr(
        "app.bootstrap.build_calendar_service",
        lambda root: google_service,
    )
    monkeypatch.setattr("app.bootstrap.build_yandex_client", lambda root: object())
    monkeypatch.setattr(
        "app.bootstrap.load_yandex_sync_calendar",
        lambda client, root: yandex_calendar,
    )

    def prepare_calendars(root):
        google_service.events_resource.items.clear()
        yandex_calendar.items.clear()
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

    def adapter_builder(**kwargs):
        adapter_flags.append(
            (kwargs["use_real_google"], kwargs["use_real_yandex"])
        )
        return build_sync_adapters(**kwargs)

    result = run_live_demo(
        tmp_path,
        dependencies=LiveDemoDependencies(
            adapter_builder=adapter_builder,
            prerequisite_checker=lambda root: None,
            calendar_preparer=prepare_calendars,
        ),
    )

    output = capsys.readouterr().out
    assert result.lines[0] == "LIVE DEMO PASSED"
    assert "Google Calendar: create/update/delete OK" in output
    assert "Yandex Calendar: create/update/delete OK" in output
    assert "Google <-> Yandex sync OK" in output
    assert "Duplicate protection OK" in output
    assert adapter_flags
    assert all(flags == (True, True) for flags in adapter_flags)


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
    assert "Traceback" not in message


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

    def _with_google_fields(self, event_id, body):
        payload = dict(body)
        payload.update(
            {
                "id": event_id,
                "updated": "2026-07-01T09:00:00Z",
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
