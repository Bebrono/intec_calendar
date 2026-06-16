from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.storage.database import EventMappingRecord, SyncLogRecord


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
