from __future__ import annotations

import argparse

from app.bootstrap import build_database, build_sync_adapters
from app.config import PROJECT_ROOT, ensure_project_dirs
from app.logger import configure_logger
from app.services.demo import run_demo
from app.services.google_calendar_config import (
    clear_sync_calendar,
    create_sync_calendar,
)
from app.services.google_integration_demo import run_google_integration_demo
from app.services.google_oauth import (
    build_calendar_service,
    create_authorization_url,
    finish_authorization,
)
from app.services.google_smoke_test import run_google_smoke_test
from app.services.sync_service import SyncService


def main() -> None:
    parser = argparse.ArgumentParser(description="Calendar Sync Service prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="Synchronize calendars")
    sync_parser.add_argument(
        "--real-google",
        action="store_true",
        help="Use real Google Calendar instead of google_developer_2.json",
    )
    subparsers.add_parser("demo", help="Run deterministic demo scenario")

    google_parser = subparsers.add_parser("google", help="Google Calendar tools")
    google_subparsers = google_parser.add_subparsers(
        dest="google_command",
        required=True,
    )
    google_subparsers.add_parser("auth-url", help="Print Google OAuth URL")
    auth_finish_parser = google_subparsers.add_parser(
        "auth-finish",
        help="Exchange Google OAuth redirect URL or code for token",
    )
    auth_finish_parser.add_argument("auth_response_or_code")
    smoke_parser = google_subparsers.add_parser(
        "smoke-test",
        help="Create, update, and delete a temporary Google Calendar event",
    )
    smoke_parser.add_argument("--calendar-id", default="primary")
    google_subparsers.add_parser(
        "create-sync-calendar",
        help="Create or reuse a dedicated Google sync calendar",
    )
    google_subparsers.add_parser(
        "clear-sync-calendar",
        help="Remove events from the dedicated Google sync calendar",
    )
    google_subparsers.add_parser(
        "integration-demo",
        help="Run JSON <-> Google live synchronization demo",
    )
    args = parser.parse_args()

    if args.command == "demo":
        run_demo(PROJECT_ROOT)
        return

    if args.command == "google":
        if args.google_command == "auth-url":
            print(create_authorization_url(PROJECT_ROOT))
            print(
                "\nOpen this URL, allow access, then run:\n"
                'python main.py google auth-finish "<final_localhost_url_or_code>"'
            )
            return

        if args.google_command == "auth-finish":
            token_path = finish_authorization(args.auth_response_or_code, PROJECT_ROOT)
            print(f"Google token saved to {token_path}")
            return

        if args.google_command == "smoke-test":
            service = build_calendar_service(PROJECT_ROOT)
            result = run_google_smoke_test(
                service,
                calendar_id=args.calendar_id,
            )
            print("Google Calendar smoke-test complete:")
            print(f"- created event id: {result.created_event_id}")
            print(f"- created title: {result.created_title}")
            print(f"- updated title: {result.updated_title}")
            print(f"- deleted status: {result.deleted_status}")
            return

        if args.google_command == "create-sync-calendar":
            service = build_calendar_service(PROJECT_ROOT)
            result = create_sync_calendar(service, root=PROJECT_ROOT)
            action = "Created" if result.created else "Using existing"
            print(f"{action} Google sync calendar:")
            print(f"- summary: {result.config.summary}")
            print(f"- calendar_id: {result.config.calendar_id}")
            return

        if args.google_command == "clear-sync-calendar":
            service = build_calendar_service(PROJECT_ROOT)
            deleted_count = clear_sync_calendar(service, root=PROJECT_ROOT)
            print(f"Removed {deleted_count} events from Google sync calendar")
            return

        if args.google_command == "integration-demo":
            run_google_integration_demo(PROJECT_ROOT)
            return

    ensure_project_dirs(PROJECT_ROOT)
    logger = configure_logger(PROJECT_ROOT / "logs" / "sync.log")
    database = build_database(PROJECT_ROOT)
    adapters = build_sync_adapters(
        root=PROJECT_ROOT,
        use_real_google=args.real_google,
    )
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
