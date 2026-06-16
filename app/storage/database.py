from __future__ import annotations

from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker


Base = declarative_base()


class EventMappingRecord(Base):
    __tablename__ = "event_mappings"
    __table_args__ = (
        UniqueConstraint(
            "calendar_owner",
            "calendar_system",
            "external_event_id",
            name="uq_event_mapping_external_event",
        ),
    )

    id = Column(Integer, primary_key=True)
    sync_group_id = Column(String, nullable=False, index=True)
    calendar_owner = Column(String, nullable=False)
    calendar_system = Column(String, nullable=False)
    external_event_id = Column(String, nullable=False, index=True)
    is_original = Column(Boolean, nullable=False, default=False)
    last_synced_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="active")
    last_event_updated_at = Column(DateTime, nullable=True)


class SyncLogRecord(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True)
    level = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

    def reset_db(self) -> None:
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
