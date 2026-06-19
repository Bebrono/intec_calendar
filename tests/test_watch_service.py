import io
import logging

import pytest

from app.services.sync_service import SyncResult
from app.services.watch_service import (
    WatchPrerequisiteError,
    _build_live_sync_runner,
    run_watch,
)


def test_watch_runs_multiple_cycles_with_interval():
    calls = []
    sleeps = []
    output = io.StringIO()

    def sync_once():
        calls.append("sync")
        return SyncResult(groups_processed=1, events_created=len(calls))

    run_watch(
        interval_seconds=10,
        output=output,
        sleep=sleeps.append,
        max_cycles=3,
        sync_once=sync_once,
    )

    assert calls == ["sync", "sync", "sync"]
    assert sleeps == [10, 10]
    assert output.getvalue().count("Synchronization complete") == 3


def test_watch_is_quiet_when_cycle_has_no_changes():
    output = io.StringIO()

    run_watch(
        interval_seconds=10,
        output=output,
        sleep=lambda _: None,
        max_cycles=1,
        sync_once=lambda: SyncResult(groups_processed=1),
    )

    assert "Synchronization complete" not in output.getvalue()


def test_watch_stops_cleanly_on_keyboard_interrupt():
    output = io.StringIO()

    def sync_once():
        raise KeyboardInterrupt

    run_watch(
        interval_seconds=10,
        output=output,
        sleep=lambda _: None,
        sync_once=sync_once,
    )

    assert "Watch stopped by user." in output.getvalue()


def test_watch_builds_real_google_and_yandex_adapters(monkeypatch, tmp_path):
    captured = {}

    def fake_build_sync_adapters(**kwargs):
        captured.update(kwargs)
        return ["adapter"]

    class FakeSyncService:
        def __init__(self, *, adapters, database, logger):
            self.adapters = adapters
            self.database = database
            self.logger = logger

        def sync(self):
            return SyncResult(groups_processed=1)

    monkeypatch.setattr(
        "app.services.watch_service.build_sync_adapters",
        fake_build_sync_adapters,
    )
    monkeypatch.setattr("app.services.watch_service.build_database", lambda root: object())
    monkeypatch.setattr(
        "app.services.watch_service.configure_logger",
        lambda path, **_: logging.getLogger("watch-test"),
    )
    monkeypatch.setattr("app.services.watch_service.SyncService", FakeSyncService)

    runner = _build_live_sync_runner(tmp_path)
    result = runner()

    assert result.groups_processed == 1
    assert captured["root"] == tmp_path
    assert captured["use_real_google"] is True
    assert captured["use_real_yandex"] is True


def test_watch_missing_credentials_are_reported_as_prerequisite_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.watch_service.build_sync_adapters",
        lambda **_: (_ for _ in ()).throw(FileNotFoundError("Google token not found")),
    )

    with pytest.raises(WatchPrerequisiteError) as exc_info:
        run_watch(
            tmp_path,
            output=io.StringIO(),
            sleep=lambda _: None,
            max_cycles=1,
        )

    assert "Google token not found" in str(exc_info.value)
