from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.adapters import CalendarAdapter
from app.models import CalendarEvent
from app.services.event_mapper import EventMapper
from app.storage import (
    Database,
    MappingRepository,
    SyncedEventRepository,
    SyncLogRepository,
)
from app.storage.database import EventMappingRecord, SyncedEventRecord


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

    def sync(self) -> SyncResult:
        self.database.init_db()
        result = SyncResult()

        with self.database.SessionLocal() as session:
            mappings = MappingRepository(session)
            synced_events = SyncedEventRepository(session)
            logs = SyncLogRepository(session)
            self._log(logs, "info", "Synchronization started")

            try:
                loaded_events = self._load_events(logs)
                groups = self._attach_sync_groups(loaded_events, mappings, logs)
                events_by_key = self._events_by_key(loaded_events)

                deleted_groups = self._apply_deletions_to_canonical_store(
                    groups,
                    events_by_key,
                    mappings,
                    synced_events,
                    logs,
                )
                self._apply_active_changes_to_canonical_store(
                    groups,
                    deleted_groups,
                    synced_events,
                    logs,
                )
                self._project_canonical_store(
                    synced_events.list_all(),
                    events_by_key,
                    mappings,
                    synced_events,
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

            if mapping is None and event.status in TERMINAL_STATUSES:
                self._log(
                    logs,
                    "info",
                    (
                        "Ignored unmapped terminal event "
                        f"{adapter.system}/{adapter.owner}/{event.id}"
                    ),
                )
                continue

            if mapping is not None:
                sync_group_id = mapping.sync_group_id
                if event.status not in TERMINAL_STATUSES:
                    original_source = self._resolve_original_source_system(
                        sync_group_id,
                        mappings,
                        fallback=self.mapper.extract_source(event.description)
                        or event.source_system,
                    )
                    item.event = self._ensure_event_metadata(
                        adapter,
                        event,
                        sync_group_id=sync_group_id,
                        original_source_system=original_source,
                    )
                    event = item.event
                item.mapping = mappings.update_mapping(
                    mapping,
                    status=event.status,
                    last_event_updated_at=event.updated_at,
                )
            elif description_sync_id:
                sync_group_id = description_sync_id
                source_marker = self.mapper.extract_source(event.description)
                original_source = source_marker or event.source_system
                item.mapping = mappings.upsert_mapping(
                    sync_group_id=sync_group_id,
                    calendar_owner=adapter.owner,
                    calendar_system=adapter.system,
                    external_event_id=event.id,
                    is_original=self._should_recover_as_original(
                        sync_group_id,
                        event,
                        original_source_system=original_source,
                        mappings=mappings,
                    ),
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
                item.event = self._ensure_event_metadata(
                    adapter,
                    event,
                    sync_group_id=sync_group_id,
                    original_source_system=event.source_system,
                )
                event = item.event
                item.mapping = mappings.upsert_mapping(
                    sync_group_id=sync_group_id,
                    calendar_owner=adapter.owner,
                    calendar_system=adapter.system,
                    external_event_id=event.id,
                    is_original=True,
                    status=event.status,
                    last_event_updated_at=event.updated_at,
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

    def _apply_deletions_to_canonical_store(
        self,
        groups: dict[str, list[LoadedEvent]],
        events_by_key: dict[tuple[str, str, str], LoadedEvent],
        mappings: MappingRepository,
        synced_events: SyncedEventRepository,
        logs: SyncLogRepository,
    ) -> set[str]:
        deleted_groups: set[str] = set()

        for sync_group_id, group_events in groups.items():
            terminal_event = self._find_terminal_event(group_events)
            if terminal_event is None:
                continue

            deleted_event = self._canonical_event_from(
                terminal_event.event,
                sync_group_id=sync_group_id,
                status="deleted",
            )
            synced_events.mark_deleted(
                sync_group_id=sync_group_id,
                event=deleted_event,
                deleted_at=deleted_event.updated_at,
            )
            deleted_groups.add(sync_group_id)
            self._log(
                logs,
                "info",
                f"Canonical event {sync_group_id} marked deleted from terminal event",
            )

        for mapping in mappings.list_all():
            if mapping.status in TERMINAL_STATUSES:
                record = synced_events.get(mapping.sync_group_id)
                group_events = groups.get(mapping.sync_group_id, [])
                latest_event = self._latest_event(group_events)
                if record is not None:
                    deleted_event = synced_events.to_calendar_event(record).model_copy(
                        update={
                            "status": "deleted",
                            "updated_at": mapping.last_event_updated_at
                            or self._current_timestamp(),
                        }
                    )
                    synced_events.mark_deleted(
                        sync_group_id=mapping.sync_group_id,
                        event=deleted_event,
                        deleted_at=deleted_event.updated_at,
                    )
                elif latest_event is not None:
                    deleted_event = self._canonical_event_from(
                        latest_event.event,
                        sync_group_id=mapping.sync_group_id,
                        status="deleted",
                        updated_at=mapping.last_event_updated_at
                        or self._current_timestamp(),
                    )
                    synced_events.mark_deleted(
                        sync_group_id=mapping.sync_group_id,
                        event=deleted_event,
                        deleted_at=deleted_event.updated_at,
                    )
                deleted_groups.add(mapping.sync_group_id)
                continue

            if (
                mapping.calendar_owner,
                mapping.calendar_system,
            ) not in self.adapters_by_calendar:
                continue
            event_key = (
                mapping.calendar_owner,
                mapping.calendar_system,
                mapping.external_event_id,
            )
            if event_key in events_by_key:
                continue

            record = synced_events.get(mapping.sync_group_id)
            group_events = groups.get(mapping.sync_group_id, [])
            latest_event = self._latest_event(group_events)
            if record is not None:
                deleted_event = synced_events.to_calendar_event(record).model_copy(
                    update={
                        "status": "deleted",
                        "updated_at": self._current_timestamp(),
                    }
                )
                synced_events.mark_deleted(
                    sync_group_id=mapping.sync_group_id,
                    event=deleted_event,
                    deleted_at=deleted_event.updated_at,
                )
            elif latest_event is not None:
                deleted_event = self._canonical_event_from(
                    latest_event.event,
                    sync_group_id=mapping.sync_group_id,
                    status="deleted",
                    updated_at=self._current_timestamp(),
                )
                synced_events.mark_deleted(
                    sync_group_id=mapping.sync_group_id,
                    event=deleted_event,
                    deleted_at=deleted_event.updated_at,
                )
            else:
                mappings.update_mapping(
                    mapping,
                    status="deleted",
                    last_event_updated_at=self._current_timestamp(),
                )
                continue

            deleted_groups.add(mapping.sync_group_id)
            self._log(
                logs,
                "info",
                (
                    "Detected missing mapped event "
                    f"{mapping.external_event_id} in "
                    f"{mapping.calendar_system}/{mapping.calendar_owner}; "
                    f"canonical group {mapping.sync_group_id} marked deleted"
                ),
            )

        return deleted_groups

    def _apply_active_changes_to_canonical_store(
        self,
        groups: dict[str, list[LoadedEvent]],
        deleted_groups: set[str],
        synced_events: SyncedEventRepository,
        logs: SyncLogRepository,
    ) -> None:
        for sync_group_id, group_events in groups.items():
            if sync_group_id in deleted_groups:
                continue

            active_events = [
                item for item in group_events if item.event.status not in TERMINAL_STATUSES
            ]
            if not active_events:
                continue

            current_record = synced_events.get(sync_group_id)
            current_event = (
                synced_events.to_calendar_event(current_record)
                if current_record is not None
                else None
            )
            if current_event is None:
                latest = self._latest_event(active_events)
            else:
                changed_events = [
                    item
                    for item in active_events
                    if self._canonical_fields_differ(item.event, current_event)
                    and item.event.updated_at >= current_event.updated_at
                ]
                latest = self._latest_event(changed_events)

            if latest is None:
                continue

            canonical_event = self._canonical_event_from(
                latest.event,
                sync_group_id=sync_group_id,
                status="confirmed",
            )
            synced_events.upsert_event(
                sync_group_id=sync_group_id,
                event=canonical_event,
            )
            self._log(
                logs,
                "info",
                (
                    f"Canonical event {sync_group_id} saved from "
                    f"{latest.adapter.system}/{latest.adapter.owner}/{latest.event.id}"
                ),
            )

    def _project_canonical_store(
        self,
        records: list[SyncedEventRecord],
        events_by_key: dict[tuple[str, str, str], LoadedEvent],
        mappings: MappingRepository,
        synced_events: SyncedEventRepository,
        logs: SyncLogRepository,
        result: SyncResult,
    ) -> None:
        for record in records:
            result.groups_processed += 1
            canonical_event = synced_events.to_calendar_event(record)
            group_mappings = mappings.get_by_sync_group(record.sync_group_id)

            if canonical_event.status in TERMINAL_STATUSES:
                self._project_deleted_event(
                    record.sync_group_id,
                    canonical_event,
                    group_mappings,
                    events_by_key,
                    mappings,
                    logs,
                    result,
                )
                continue

            self._project_active_event(
                record.sync_group_id,
                canonical_event,
                group_mappings,
                events_by_key,
                mappings,
                synced_events,
                logs,
                result,
            )

    def _project_active_event(
        self,
        sync_group_id: str,
        canonical_event: CalendarEvent,
        group_mappings: list[EventMappingRecord],
        events_by_key: dict[tuple[str, str, str], LoadedEvent],
        mappings: MappingRepository,
        synced_events: SyncedEventRepository,
        logs: SyncLogRepository,
        result: SyncResult,
    ) -> None:
        mapping_by_calendar = {
            (mapping.calendar_owner, mapping.calendar_system): mapping
            for mapping in group_mappings
        }
        original_source = self._resolve_original_source_system(
            sync_group_id,
            mappings,
            fallback=canonical_event.source_system,
        )

        for adapter in self.adapters:
            calendar_key = (adapter.owner, adapter.system)
            mapping = mapping_by_calendar.get(calendar_key)
            loaded_current = None
            if mapping is not None:
                loaded_current = events_by_key.get(
                    (adapter.owner, adapter.system, mapping.external_event_id)
                )

            if mapping is None or (
                mapping.status in TERMINAL_STATUSES and loaded_current is None
            ):
                expected = self.mapper.clone_for_calendar(
                    canonical_event,
                    event_id="",
                    source_system=adapter.system,
                    source_owner=adapter.owner,
                    sync_group_id=sync_group_id,
                    original_source_system=original_source,
                )
                created = adapter.create_event(expected)
                if mapping is None:
                    mappings.upsert_mapping(
                        sync_group_id=sync_group_id,
                        calendar_owner=adapter.owner,
                        calendar_system=adapter.system,
                        external_event_id=created.id,
                        is_original=False,
                        status=created.status,
                        last_event_updated_at=created.updated_at,
                    )
                else:
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
                    f"Created copy {created.id} in {adapter.system}/{adapter.owner}",
                )
                continue

            if mapping is None:
                continue

            if loaded_current is None:
                self._log(
                    logs,
                    "info",
                    (
                        f"Mapped event {mapping.external_event_id} is missing in "
                        f"{adapter.system}/{adapter.owner}; waiting for next cycle"
                    ),
                )
                continue

            expected = self.mapper.clone_for_calendar(
                canonical_event,
                event_id=mapping.external_event_id,
                source_system=adapter.system,
                source_owner=adapter.owner,
                sync_group_id=sync_group_id,
                original_source_system=original_source,
            )
            if self._needs_update(loaded_current.event, expected):
                try:
                    updated = adapter.update_event(mapping.external_event_id, expected)
                except Exception as exc:
                    if not self._is_missing_event_error(exc):
                        raise
                    deleted_event = canonical_event.model_copy(
                        update={
                            "status": "deleted",
                            "updated_at": self._current_timestamp(),
                        }
                    )
                    synced_events.mark_deleted(
                        sync_group_id=sync_group_id,
                        event=deleted_event,
                        deleted_at=deleted_event.updated_at,
                    )
                    mappings.update_mapping(
                        mapping,
                        status="deleted",
                        last_event_updated_at=deleted_event.updated_at,
                    )
                    events_without_missing = dict(events_by_key)
                    events_without_missing.pop(
                        (adapter.owner, adapter.system, mapping.external_event_id),
                        None,
                    )
                    self._log(
                        logs,
                        "info",
                        (
                            f"Mapped event {mapping.external_event_id} disappeared "
                            f"from {adapter.system}/{adapter.owner} during update"
                        ),
                    )
                    self._project_deleted_event(
                        sync_group_id,
                        deleted_event,
                        mappings.get_by_sync_group(sync_group_id),
                        events_without_missing,
                        mappings,
                        logs,
                        result,
                    )
                    continue
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

    def _project_deleted_event(
        self,
        sync_group_id: str,
        canonical_event: CalendarEvent,
        group_mappings: list[EventMappingRecord],
        events_by_key: dict[tuple[str, str, str], LoadedEvent],
        mappings: MappingRepository,
        logs: SyncLogRepository,
        result: SyncResult,
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
                    status="deleted",
                    last_event_updated_at=canonical_event.updated_at,
                )
                continue

            if loaded_current.event.status in TERMINAL_STATUSES:
                mappings.update_mapping(
                    mapping,
                    status="deleted",
                    last_event_updated_at=loaded_current.event.updated_at,
                )
                continue

            try:
                deleted = adapter.delete_event(mapping.external_event_id)
            except Exception as exc:
                if not self._is_missing_event_error(exc):
                    raise
                deleted = canonical_event.model_copy(update={"status": "deleted"})

            mappings.update_mapping(
                mapping,
                status="deleted",
                last_event_updated_at=deleted.updated_at,
            )
            result.events_deleted += 1
            self._log(
                logs,
                "info",
                (
                    f"Deleted event {mapping.external_event_id} from "
                    f"{adapter.system}/{adapter.owner}"
                ),
            )

    def _events_by_key(
        self,
        loaded_events: list[LoadedEvent],
    ) -> dict[tuple[str, str, str], LoadedEvent]:
        return {
            (item.adapter.owner, item.adapter.system, item.event.id): item
            for item in loaded_events
            if item.sync_group_id is not None
        }

    def _canonical_event_from(
        self,
        event: CalendarEvent,
        *,
        sync_group_id: str,
        status: str,
        updated_at: datetime | None = None,
    ) -> CalendarEvent:
        return event.model_copy(
            update={
                "id": sync_group_id,
                "description": self.mapper.strip_sync_metadata(event.description),
                "status": status,
                "updated_at": updated_at or event.updated_at,
            }
        )

    def _canonical_fields_differ(
        self,
        current: CalendarEvent,
        canonical: CalendarEvent,
    ) -> bool:
        return any(
            (
                current.title != canonical.title,
                self.mapper.strip_sync_metadata(current.description)
                != (canonical.description or ""),
                current.start_time != canonical.start_time,
                current.end_time != canonical.end_time,
                current.organizer != canonical.organizer,
                current.attendees != canonical.attendees,
                current.status != canonical.status,
            )
        )

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
            )
        )

    def _find_terminal_event(
        self,
        group_events: list[LoadedEvent],
    ) -> LoadedEvent | None:
        terminal_events = [
            item for item in group_events if item.event.status in TERMINAL_STATUSES
        ]
        return self._latest_event(terminal_events)

    def _latest_event(self, events: list[LoadedEvent]) -> LoadedEvent | None:
        if not events:
            return None
        return max(
            events,
            key=lambda item: (
                item.event.updated_at,
                bool(item.mapping and item.mapping.is_original),
            ),
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

    def _should_recover_as_original(
        self,
        sync_group_id: str,
        event: CalendarEvent,
        *,
        original_source_system: str,
        mappings: MappingRepository,
    ) -> bool:
        if mappings.get_original_mapping(sync_group_id) is not None:
            return False
        return event.source_system == original_source_system

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

    def _is_missing_event_error(self, exc: Exception) -> bool:
        if isinstance(exc, KeyError):
            return True
        if exc.__class__.__name__ == "NotFoundError":
            return True
        return "not found" in str(exc).lower()

    def _new_sync_group_id(self) -> str:
        return f"sync_{uuid4().hex[:12]}"

    def _current_timestamp(self) -> datetime:
        return datetime.now(UTC).replace(microsecond=0, tzinfo=None)

    def _log(self, logs: SyncLogRepository, level: str, message: str) -> None:
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message)
        logs.add(level, message)
