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
from app.services.live_demo import (
    LiveDemoError,
    LiveDemoPrerequisiteError,
    run_live_demo,
)
from app.services.sync_service import SyncService
from app.services.yandex_calendar_config import (
    build_yandex_client,
    clear_sync_calendar as clear_yandex_sync_calendar,
    create_sync_calendar as create_yandex_sync_calendar,
    load_sync_calendar as load_yandex_sync_calendar,
)
from app.services.yandex_integration_demo import run_yandex_integration_demo
from app.services.yandex_smoke_test import run_yandex_smoke_test


def main() -> None:
    parser = argparse.ArgumentParser(description="Calendar Sync Service prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="Synchronize calendars")
    sync_parser.add_argument(
        "--real-google",
        action="store_true",
        help="Use real Google Calendar instead of google_developer_2.json",
    )
    sync_parser.add_argument(
        "--real-yandex",
        action="store_true",
        help="Use real Yandex Calendar instead of yandex_developer_1.json",
    )
    subparsers.add_parser("demo", help="Run deterministic demo scenario")
    subparsers.add_parser(
        "live-demo",
        help="Run Google + Yandex live verification scenario",
    )

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

    yandex_parser = subparsers.add_parser("yandex", help="Yandex Calendar tools")
    yandex_subparsers = yandex_parser.add_subparsers(
        dest="yandex_command",
        required=True,
    )
    yandex_subparsers.add_parser("check-auth", help="Check Yandex CalDAV auth")
    yandex_subparsers.add_parser(
        "create-sync-calendar",
        help="Create or reuse a dedicated Yandex sync calendar",
    )
    yandex_subparsers.add_parser(
        "clear-sync-calendar",
        help="Remove events from the dedicated Yandex sync calendar",
    )
    yandex_subparsers.add_parser(
        "smoke-test",
        help="Create, update, and soft-delete a temporary Yandex Calendar event",
    )
    yandex_subparsers.add_parser(
        "integration-demo",
        help="Run JSON <-> Yandex live synchronization demo",
    )
    args = parser.parse_args()

    if args.command == "demo":
        run_demo(PROJECT_ROOT)
        return

    if args.command == "live-demo":
        try:
            run_live_demo(PROJECT_ROOT)
        except LiveDemoPrerequisiteError as exc:
            print("LIVE DEMO CANNOT START")
            print(f"- {exc}")
            raise SystemExit(2) from None
        except LiveDemoError as exc:
            print("LIVE DEMO FAILED")
            print(f"- {exc}")
            raise SystemExit(1) from None
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

    if args.command == "yandex":
        if args.yandex_command == "check-auth":
            client = build_yandex_client(PROJECT_ROOT)
            calendars = client.principal().calendars()
            print(f"Yandex CalDAV auth OK, calendars found: {len(calendars)}")
            return

        if args.yandex_command == "create-sync-calendar":
            client = build_yandex_client(PROJECT_ROOT)
            result = create_yandex_sync_calendar(client, root=PROJECT_ROOT)
            action = "Created" if result.created else "Using existing"
            print(f"{action} Yandex sync calendar:")
            print(f"- name: {result.config.name}")
            print(f"- calendar_url: {result.config.calendar_url}")
            return

        if args.yandex_command == "clear-sync-calendar":
            client = build_yandex_client(PROJECT_ROOT)
            deleted_count = clear_yandex_sync_calendar(client, root=PROJECT_ROOT)
            print(f"Removed {deleted_count} events from Yandex sync calendar")
            return

        if args.yandex_command == "smoke-test":
            client = build_yandex_client(PROJECT_ROOT)
            calendar = load_yandex_sync_calendar(client, root=PROJECT_ROOT)
            result = run_yandex_smoke_test(calendar)
            print("Yandex Calendar smoke-test complete:")
            print(f"- created event id: {result.created_event_id}")
            print(f"- created title: {result.created_title}")
            print(f"- updated title: {result.updated_title}")
            print(f"- deleted status: {result.deleted_status}")
            return

        if args.yandex_command == "integration-demo":
            run_yandex_integration_demo(PROJECT_ROOT)
            return

    ensure_project_dirs(PROJECT_ROOT)
    logger = configure_logger(PROJECT_ROOT / "logs" / "sync.log")
    database = build_database(PROJECT_ROOT)
    adapters = build_sync_adapters(
        root=PROJECT_ROOT,
        use_real_google=args.real_google,
        use_real_yandex=args.real_yandex,
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
