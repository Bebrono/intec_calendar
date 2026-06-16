from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CalendarEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    organizer: str
    attendees: list[str] = Field(default_factory=list)
    source_system: str
    source_owner: str
    status: str = "confirmed"
    updated_at: datetime

    def with_calendar_identity(
        self,
        *,
        event_id: str,
        source_system: str,
        source_owner: str,
    ) -> "CalendarEvent":
        return self.model_copy(
            update={
                "id": event_id,
                "source_system": source_system,
                "source_owner": source_owner,
            }
        )
