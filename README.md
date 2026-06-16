# Calendar Sync Service

Prototype Python service for synchronizing calendar events between team members who use different calendar ecosystems.

The first version uses JSON files instead of real Yandex Calendar, Google Calendar, and Outlook Calendar APIs. This keeps the prototype runnable without OAuth, tokens, external accounts, or provider permissions while preserving the adapter boundary needed for future API clients.

## What It Does

- Reads events from four calendar files in `data/output`.
- Converts every event to a shared `CalendarEvent` model.
- Creates missing copies in the other calendars.
- Propagates updates using the newest `updated_at` value inside a sync group.
- Propagates soft deletion by setting `status` to `deleted` or `cancelled`.
- Prevents duplicate and cyclic synchronization through SQLite mappings and `[SYNC_ID: ...]` metadata.
- Writes logs to the console, `logs/sync.log`, and the `sync_logs` SQLite table.

## Architecture

- `CalendarAdapter` defines the calendar interface: `get_events`, `create_event`, `update_event`, `delete_event`.
- `FileCalendarAdapter` is the temporary JSON-backed implementation.
- `EventMapper` converts JSON payloads to `CalendarEvent` objects and manages sync metadata in descriptions.
- `SyncService` contains the business logic and does not depend on JSON storage directly.
- `Storage` uses SQLite and SQLAlchemy for `event_mappings` and `sync_logs`.

The file adapter can later be replaced with `GoogleCalendarAdapter`, `OutlookCalendarAdapter`, or `YandexCalendarAdapter` as long as they implement the same adapter interface.

## Setup

Requires Python 3.11+.

```bash
pip install -r requirements.txt
```

## Commands

Run synchronization against the working calendar files:

```bash
python main.py sync
```

Run the deterministic demo scenario:

```bash
python main.py demo
```

The demo resets `data/output`, `data/sync.db`, and `logs/sync.log`, then shows:

1. creation of an Outlook event and propagation to the other calendars;
2. update propagation;
3. soft deletion propagation.

## Calendar Files

Input fixtures live in `data/input`. Working calendars live in `data/output`:

- `outlook_manager.json`
- `google_developer_2.json`
- `yandex_developer_1.json`
- `yandex_leader.json`

Each file stores a JSON array of events. After synchronization, copied events include metadata in `description`:

```text
[SYNC_ID: sync_xxx]
[SOURCE: outlook]
```

## Checking Results

After `python main.py sync`, inspect:

- JSON files in `data/output` for created or updated copies;
- `data/sync.db` for event mappings and DB logs;
- `logs/sync.log` for console-equivalent log output.

Run tests with:

```bash
pytest
```
