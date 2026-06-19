from __future__ import annotations

import sys
import time
from collections.abc import Callable
from datetime import datetime
import logging
from pathlib import Path
from typing import TextIO

from app.bootstrap import build_database, build_sync_adapters
from app.config import PROJECT_ROOT, ensure_project_dirs
from app.logger import configure_logger
from app.services.sync_service import SyncResult, SyncService


class WatchPrerequisiteError(RuntimeError):
    """Raised when live watch cannot be started because local access is missing."""


def run_watch(
    root: Path = PROJECT_ROOT,
    *,
    interval_seconds: int = 10,
    output: TextIO | None = None,
    sleep: Callable[[int], None] = time.sleep,
    max_cycles: int | None = None,
    sync_once: Callable[[], SyncResult] | None = None,
) -> None:
    if interval_seconds <= 0:
        raise ValueError("Watch interval must be greater than zero")

    stream = output or sys.stdout
    runner = sync_once or _build_live_sync_runner(root)

    print(
        f"Watch started: Google + Yandex + JSON sync every {interval_seconds}s.",
        file=stream,
    )
    print("Press Ctrl+C to stop.", file=stream)

    cycles_completed = 0
    try:
        while max_cycles is None or cycles_completed < max_cycles:
            try:
                result = runner()
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(
                    f"[{_timestamp()}] WATCH CYCLE FAILED: {exc}",
                    file=stream,
                )
            else:
                if not _has_changes(result):
                    cycles_completed += 1
                    if max_cycles is not None and cycles_completed >= max_cycles:
                        break
                    sleep(interval_seconds)
                    continue
                print(
                    (
                        f"[{_timestamp()}] Synchronization complete: "
                        f"groups={result.groups_processed}, "
                        f"created={result.events_created}, "
                        f"updated={result.events_updated}, "
                        f"deleted={result.events_deleted}"
                    ),
                    file=stream,
                )

            cycles_completed += 1
            if max_cycles is not None and cycles_completed >= max_cycles:
                break
            sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nWatch stopped by user.", file=stream)


def _build_live_sync_runner(root: Path) -> Callable[[], SyncResult]:
    try:
        ensure_project_dirs(root)
        logger = configure_logger(
            root / "logs" / "sync.log",
            console_level=logging.CRITICAL,
        )
        database = build_database(root)
        adapters = build_sync_adapters(
            root=root,
            use_real_google=True,
            use_real_yandex=True,
        )
    except Exception as exc:
        raise WatchPrerequisiteError(str(exc)) from exc

    service = SyncService(
        adapters=adapters,
        database=database,
        logger=logger,
    )
    return service.sync


def _timestamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _has_changes(result: SyncResult) -> bool:
    return any(
        (
            result.events_created,
            result.events_updated,
            result.events_deleted,
        )
    )
