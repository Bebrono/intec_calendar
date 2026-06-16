from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from app.adapters import CalendarAdapter
from app.models import CalendarEvent
from app.services.event_mapper import EventMapper
from app.storage import Database, MappingRepository, SyncLogRepository
from app.storage.database import EventMappingRecord


TERMINAL_STATUSES = {"deleted", "cancelled"}


@dataclass
class LoadedEvent:
    adapter: CalendarAdapter
    event: CalendarEvent
    mapping: EventMappingRecord | None = None
    sync_group_id: str | None = None


@dataclass
class SyncResult:
    groups_processed: int = 0
    events_created: int = 0
    events_updated: int = 0
    events_deleted: int = 0


class SyncService:
    def __init__(
        self,
        *,
        adapters: list[CalendarAdapter],
        database: Database,
        logger: logging.Logger,
        mapper: EventMapper | None = None,
    ) -> None:
        self.adapters = adapters
        self.database = database
        self.logger = logger
        self.mapper = mapper or EventMapper()
        self.adapters_by_calendar = {
            (adapter.owner, adapter.system): adapter for adapter in adapters
        }
        self.known_owners = {adapter.owner for adapter in adapters}

    def sync(self) -> SyncResult:
        self.database.init_db()
        result = SyncResult()

        with self.database.SessionLocal() as session:
            mappings = MappingRepository(session)
            logs = SyncLogRepository(session)
            self._log(logs, "info", "Synchronization started")

            try:
                loaded_events = self._load_events(logs)
                groups = self._attach_sync_groups(loaded_events, mappings, logs)
                events_by_key = {
                    (item.adapter.owner, item.adapter.system, item.event.id): item
                    for item in loaded_events
                }

                for sync_group_id, group_events in groups.items():
                    self._sync_group(
                        sync_group_id,
                        group_events,
                        events_by_key,
                        mappings,
                        logs,
                        result,
                    )

                session.commit()
            except Exception as exc:
                session.rollback()
                self.logger.exception("Synchronization failed")
                try:
                    logs.add("ERROR", f"Synchronization failed: {exc}")
                    session.commit()
                except Exception:
                    session.rollback()
                raise

            self._log(
                logs,
                "info",
                (
                    "Synchronization finished: "
                    f"groups={result.groups_processed}, "
                    f"created={result.events_created}, "
                    f"updated={result.events_updated}, "
                    f"deleted={result.events_deleted}"
                ),
            )
            session.commit()

        return result

    def _load_events(self, logs: SyncLogRepository) -> list[LoadedEvent]:
        loaded: list[LoadedEvent] = []
        for adapter in self.adapters:
            try:
                events = adapter.get_events()
            except Exception as exc:
                self._log(
                    logs,
                    "error",
                    f"Cannot read calendar {adapter.system}/{adapter.owner}: {exc}",
                )
                raise

            for event in events:
                loaded.append(LoadedEvent(adapter=adapter, event=event))
            self._log(
                logs,
                "info",
                f"Loaded {len(events)} events from {adapter.system}/{adapter.owner}",
            )
        return loaded

    def _attach_sync_groups(
        self,
        loaded_events: list[LoadedEvent],
        mappings: MappingRepository,
        logs: SyncLogRepository,
    ) -> dict[str, list[LoadedEvent]]:
        groups: dict[str, list[LoadedEvent]] = {}

        for item in loaded_events:
            event = item.event
            adapter = item.adapter
            mapping = mappings.get_by_external_event(
                calendar_owner=adapter.owner,
                calendar_system=adapter.system,
                external_event_id=event.id,
            )
            description_sync_id = self.mapper.extract_sync_id(event.description)

            if mapping is not None:
                sync_group_id = mapping.sync_group_id
                original_source = self._resolve_original_source_system(
                    sync_group_id,
                    mappings,
                    fallback=event.source_system,
                )
                item.event = self._ensure_event_metadata(
                    adapter,
                    event,
                    sync_group_id=sync_group_id,
                    original_source_system=original_source,
                )
                item.mapping = mappings.update_mapping(
                    mapping,
                    status=item.event.status,
                    last_event_updated_at=item.event.updated_at,
                )
            elif description_sync_id:
                sync_group_id = description_sync_id
                source_marker = self.mapper.extract_source(event.description)
                original_source = source_marker or event.source_system
                is_original = self._is_recovered_original_candidate(
                    event,
                    original_source_system=original_source,
                    mappings=mappings,
                    sync_group_id=sync_group_id,
                )
                item.mapping = mappings.upsert_mapping(
                    sync_group_id=sync_group_id,
                    calendar_owner=adapter.owner,
                    calendar_system=adapter.system,
                    external_event_id=event.id,
                    is_original=is_original,
                    status=event.status,
                    last_event_updated_at=event.updated_at,
                )
                self._log(
                    logs,
                    "info",
                    (
                        "Recovered mapping for "
                        f"{adapter.system}/{adapter.owner}/{event.id} "
                        f"in {sync_group_id}"
                    ),
                )
            else:
                sync_group_id = self._new_sync_group_id()
                item.mapping = mappings.upsert_mapping(
                    sync_group_id=sync_group_id,
                    calendar_owner=adapter.owner,
                    calendar_system=adapter.system,
                    external_event_id=event.id,
                    is_original=True,
                    status=event.status,
                    last_event_updated_at=event.updated_at,
                )
                item.event = self._ensure_event_metadata(
                    adapter,
                    event,
                    sync_group_id=sync_group_id,
                    original_source_system=event.source_system,
                )
                self._log(
                    logs,
                    "info",
                    (
                        f"Found new event {event.id} in "
                        f"{adapter.system}/{adapter.owner}; group={sync_group_id}"
                    ),
                )

            item.sync_group_id = sync_group_id
            groups.setdefault(sync_group_id, []).append(item)

        return groups

    def _sync_group(
        self,
        sync_group_id: str,
        group_events: list[LoadedEvent],
        events_by_key: dict[tuple[str, str, str], LoadedEvent],
        mappings: MappingRepository,
        logs: SyncLogRepository,
        result: SyncResult,
    ) -> None:
        result.groups_processed += 1
        latest = max(
            group_events,
            key=lambda item: (
                item.event.updated_at,
                bool(item.mapping and item.mapping.is_original),
            ),
        )
        original_source = self._resolve_original_source_system(
            sync_group_id,
            mappings,
            fallback=self.mapper.extract_source(latest.event.description)
            or latest.event.source_system,
        )
        group_mappings = mappings.get_by_sync_group(sync_group_id)
        mapping_by_calendar = {
            (mapping.calendar_owner, mapping.calendar_system): mapping
            for mapping in group_mappings
        }

        if latest.event.status in TERMINAL_STATUSES:
            self._sync_terminal_group(
                sync_group_id,
                latest.event,
                group_mappings,
                events_by_key,
                mappings,
                logs,
                result,
                original_source,
            )
            return

        for adapter in self.adapters:
            calendar_key = (adapter.owner, adapter.system)
            mapping = mapping_by_calendar.get(calendar_key)
            expected_event_id = mapping.external_event_id if mapping else ""
            expected = self.mapper.clone_for_calendar(
                latest.event,
                event_id=expected_event_id,
                source_system=adapter.system,
                source_owner=adapter.owner,
                sync_group_id=sync_group_id,
                original_source_system=original_source,
            )

            if mapping is None:
                created = adapter.create_event(expected)
                mappings.upsert_mapping(
                    sync_group_id=sync_group_id,
                    calendar_owner=adapter.owner,
                    calendar_system=adapter.system,
                    external_event_id=created.id,
                    is_original=False,
                    status=created.status,
                    last_event_updated_at=created.updated_at,
                )
                result.events_created += 1
                self._log(
                    logs,
                    "info",
                    f"Created copy {created.id} in {adapter.system}/{adapter.owner}",
                )
                continue

            loaded_current = events_by_key.get(
                (adapter.owner, adapter.system, mapping.external_event_id)
            )
            if loaded_current is None:
                created = adapter.create_event(expected.model_copy(update={"id": ""}))
                mappings.update_mapping(
                    mapping,
                    external_event_id=created.id,
                    status=created.status,
                    last_event_updated_at=created.updated_at,
                )
                result.events_created += 1
                self._log(
                    logs,
                    "info",
                    (
                        f"Recreated missing copy {created.id} in "
                        f"{adapter.system}/{adapter.owner}"
                    ),
                )
                continue

            if self._needs_update(loaded_current.event, expected):
                updated = adapter.update_event(mapping.external_event_id, expected)
                mappings.update_mapping(
                    mapping,
                    status=updated.status,
                    last_event_updated_at=updated.updated_at,
                )
                result.events_updated += 1
                self._log(
                    logs,
                    "info",
                    f"Updated event {updated.id} in {adapter.system}/{adapter.owner}",
                )
            else:
                mappings.update_mapping(
                    mapping,
                    status=loaded_current.event.status,
                    last_event_updated_at=loaded_current.event.updated_at,
                )

    def _sync_terminal_group(
        self,
        sync_group_id: str,
        latest_event: CalendarEvent,
        group_mappings: list[EventMappingRecord],
        events_by_key: dict[tuple[str, str, str], LoadedEvent],
        mappings: MappingRepository,
        logs: SyncLogRepository,
        result: SyncResult,
        original_source: str,
    ) -> None:
        for mapping in group_mappings:
            adapter = self.adapters_by_calendar.get(
                (mapping.calendar_owner, mapping.calendar_system)
            )
            if adapter is None:
                continue

            loaded_current = events_by_key.get(
                (
                    mapping.calendar_owner,
                    mapping.calendar_system,
                    mapping.external_event_id,
                )
            )
            if loaded_current is None:
                mappings.update_mapping(
                    mapping,
                    status=latest_event.status,
                    last_event_updated_at=latest_event.updated_at,
                )
                continue

            expected = self.mapper.clone_for_calendar(
                latest_event,
                event_id=mapping.external_event_id,
                source_system=mapping.calendar_system,
                source_owner=mapping.calendar_owner,
                sync_group_id=sync_group_id,
                original_source_system=original_source,
            )
            if self._needs_update(loaded_current.event, expected):
                updated = adapter.update_event(mapping.external_event_id, expected)
                result.events_deleted += 1
                self._log(
                    logs,
                    "info",
                    (
                        f"Marked event {updated.id} as {updated.status} in "
                        f"{adapter.system}/{adapter.owner}"
                    ),
                )

            mappings.update_mapping(
                mapping,
                status=latest_event.status,
                last_event_updated_at=latest_event.updated_at,
            )

    def _ensure_event_metadata(
        self,
        adapter: CalendarAdapter,
        event: CalendarEvent,
        *,
        sync_group_id: str,
        original_source_system: str,
    ) -> CalendarEvent:
        description = self.mapper.with_sync_metadata(
            event.description,
            sync_group_id=sync_group_id,
            original_source_system=original_source_system,
        )
        if description == event.description:
            return event

        updated_event = event.model_copy(update={"description": description})
        return adapter.update_event(event.id, updated_event)

    def _needs_update(self, current: CalendarEvent, expected: CalendarEvent) -> bool:
        return any(
            (
                current.title != expected.title,
                current.description != expected.description,
                current.start_time != expected.start_time,
                current.end_time != expected.end_time,
                current.organizer != expected.organizer,
                current.attendees != expected.attendees,
                current.status != expected.status,
                current.updated_at != expected.updated_at,
            )
        )

    def _resolve_original_source_system(
        self,
        sync_group_id: str,
        mappings: MappingRepository,
        *,
        fallback: str,
    ) -> str:
        original = mappings.get_original_mapping(sync_group_id)
        return original.calendar_system if original else fallback

    def _is_recovered_original_candidate(
        self,
        event: CalendarEvent,
        *,
        original_source_system: str,
        mappings: MappingRepository,
        sync_group_id: str,
    ) -> bool:
        if mappings.get_original_mapping(sync_group_id) is not None:
            return False
        if event.source_system != original_source_system:
            return False
        if event.source_owner in self.known_owners:
            return event.source_owner == event.organizer
        return True

    def _new_sync_group_id(self) -> str:
        return f"sync_{uuid4().hex[:12]}"

    def _log(self, logs: SyncLogRepository, level: str, message: str) -> None:
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message)
        logs.add(level, message)
