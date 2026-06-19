from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarEvent
from app.storage.database import EventMappingRecord, SyncedEventRecord, SyncLogRecord


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None)


class MappingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external_event(
        self,
        *,
        calendar_owner: str,
        calendar_system: str,
        external_event_id: str,
    ) -> EventMappingRecord | None:
        statement = select(EventMappingRecord).where(
            EventMappingRecord.calendar_owner == calendar_owner,
            EventMappingRecord.calendar_system == calendar_system,
            EventMappingRecord.external_event_id == external_event_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_sync_group(self, sync_group_id: str) -> list[EventMappingRecord]:
        statement = (
            select(EventMappingRecord)
            .where(EventMappingRecord.sync_group_id == sync_group_id)
            .order_by(EventMappingRecord.id)
        )
        return list(self.session.execute(statement).scalars())

    def list_all(self) -> list[EventMappingRecord]:
        statement = select(EventMappingRecord).order_by(EventMappingRecord.id)
        return list(self.session.execute(statement).scalars())

    def get_original_mapping(self, sync_group_id: str) -> EventMappingRecord | None:
        statement = select(EventMappingRecord).where(
            EventMappingRecord.sync_group_id == sync_group_id,
            EventMappingRecord.is_original.is_(True),
        )
        return self.session.execute(statement).scalars().first()

    def upsert_mapping(
        self,
        *,
        sync_group_id: str,
        calendar_owner: str,
        calendar_system: str,
        external_event_id: str,
        is_original: bool,
        status: str = "active",
        last_event_updated_at: datetime | None = None,
    ) -> EventMappingRecord:
        record = self.get_by_external_event(
            calendar_owner=calendar_owner,
            calendar_system=calendar_system,
            external_event_id=external_event_id,
        )
        if record is None:
            record = EventMappingRecord(
                sync_group_id=sync_group_id,
                calendar_owner=calendar_owner,
                calendar_system=calendar_system,
                external_event_id=external_event_id,
                is_original=is_original,
                status=status,
                last_event_updated_at=last_event_updated_at,
                last_synced_at=now_utc(),
            )
            self.session.add(record)
            self.session.flush()
            return record

        record.sync_group_id = sync_group_id
        record.is_original = record.is_original or is_original
        record.status = status
        record.last_event_updated_at = last_event_updated_at
        record.last_synced_at = now_utc()
        self.session.flush()
        return record

    def update_mapping(
        self,
        record: EventMappingRecord,
        *,
        external_event_id: str | None = None,
        status: str | None = None,
        last_event_updated_at: datetime | None = None,
    ) -> EventMappingRecord:
        if external_event_id is not None:
            record.external_event_id = external_event_id
        if status is not None:
            record.status = status
        if last_event_updated_at is not None:
            record.last_event_updated_at = last_event_updated_at
        record.last_synced_at = now_utc()
        self.session.flush()
        return record


class SyncedEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, sync_group_id: str) -> SyncedEventRecord | None:
        return self.session.get(SyncedEventRecord, sync_group_id)

    def list_all(self) -> list[SyncedEventRecord]:
        statement = select(SyncedEventRecord).order_by(SyncedEventRecord.sync_group_id)
        return list(self.session.execute(statement).scalars())

    def upsert_event(
        self,
        *,
        sync_group_id: str,
        event: CalendarEvent,
    ) -> SyncedEventRecord:
        record = self.get(sync_group_id)
        if record is None:
            record = SyncedEventRecord(sync_group_id=sync_group_id)
            self.session.add(record)

        record.title = event.title
        record.description = event.description
        record.start_time = event.start_time
        record.end_time = event.end_time
        record.organizer = event.organizer
        record.attendees_json = json.dumps(event.attendees, ensure_ascii=False)
        record.source_system = event.source_system
        record.source_owner = event.source_owner
        record.status = event.status
        record.updated_at = event.updated_at
        record.deleted_at = None if event.status not in {"deleted", "cancelled"} else event.updated_at
        self.session.flush()
        return record

    def mark_deleted(
        self,
        *,
        sync_group_id: str,
        event: CalendarEvent | None = None,
        deleted_at: datetime | None = None,
    ) -> SyncedEventRecord:
        record = self.get(sync_group_id)
        timestamp = deleted_at or (event.updated_at if event else now_utc())

        if record is None:
            if event is None:
                raise ValueError(
                    "Cannot create deleted canonical event without event data"
                )
            record = SyncedEventRecord(sync_group_id=sync_group_id)
            self.session.add(record)
            record.title = event.title
            record.description = event.description
            record.start_time = event.start_time
            record.end_time = event.end_time
            record.organizer = event.organizer
            record.attendees_json = json.dumps(event.attendees, ensure_ascii=False)
            record.source_system = event.source_system
            record.source_owner = event.source_owner

        elif event is not None:
            record.title = event.title
            record.description = event.description
            record.start_time = event.start_time
            record.end_time = event.end_time
            record.organizer = event.organizer
            record.attendees_json = json.dumps(event.attendees, ensure_ascii=False)
            record.source_system = event.source_system
            record.source_owner = event.source_owner

        record.status = "deleted"
        record.updated_at = timestamp
        record.deleted_at = timestamp
        self.session.flush()
        return record

    def to_calendar_event(self, record: SyncedEventRecord) -> CalendarEvent:
        try:
            attendees = json.loads(record.attendees_json)
        except json.JSONDecodeError:
            attendees = []
        if not isinstance(attendees, list):
            attendees = []

        return CalendarEvent(
            id=record.sync_group_id,
            title=record.title,
            description=record.description,
            start_time=record.start_time,
            end_time=record.end_time,
            organizer=record.organizer,
            attendees=[str(attendee) for attendee in attendees],
            source_system=record.source_system,
            source_owner=record.source_owner,
            status=record.status,
            updated_at=record.updated_at,
        )


class SyncLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, level: str, message: str) -> SyncLogRecord:
        record = SyncLogRecord(
            level=level.upper(),
            message=message,
            created_at=now_utc(),
        )
        self.session.add(record)
        self.session.flush()
        return record
