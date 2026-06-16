from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import CalendarEvent


class CalendarAdapter(ABC):
    owner: str
    system: str

    @abstractmethod
    def get_events(self) -> list[CalendarEvent]:
        raise NotImplementedError

    @abstractmethod
    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        raise NotImplementedError

    @abstractmethod
    def update_event(self, event_id: str, event: CalendarEvent) -> CalendarEvent:
        raise NotImplementedError

    @abstractmethod
    def delete_event(self, event_id: str) -> CalendarEvent:
        raise NotImplementedError
