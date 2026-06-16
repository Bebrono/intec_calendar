from __future__ import annotations

import argparse

from app.bootstrap import build_database, build_file_adapters
from app.config import PROJECT_ROOT, ensure_project_dirs
from app.logger import configure_logger
from app.services.demo import run_demo
from app.services.sync_service import SyncService


def main() -> None:
    parser = argparse.ArgumentParser(description="Calendar Sync Service prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync", help="Synchronize JSON calendars")
    subparsers.add_parser("demo", help="Run deterministic demo scenario")
    args = parser.parse_args()

    if args.command == "demo":
        run_demo(PROJECT_ROOT)
        return

    ensure_project_dirs(PROJECT_ROOT)
    logger = configure_logger(PROJECT_ROOT / "logs" / "sync.log")
    database = build_database(PROJECT_ROOT)
    adapters = build_file_adapters(root=PROJECT_ROOT)
    result = SyncService(
        adapters=adapters,
        database=database,
        logger=logger,
    ).sync()

    print(
        "Synchronization complete: "
        f"groups={result.groups_processed}, "
        f"created={result.events_created}, "
        f"updated={result.events_updated}, "
        f"deleted={result.events_deleted}"
    )


if __name__ == "__main__":
    main()
