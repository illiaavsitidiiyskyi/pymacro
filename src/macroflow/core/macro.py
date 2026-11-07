"""Macro model: an ordered list of key events with timestamps."""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from macroflow.core.actions import KeyEvent


@dataclass(slots=True)
class Macro:
    """An ordered recording: key events plus when each one happened.

    Events are kept in playback order (``append`` adds to the end).  Each
    event carries its own wall-clock ``timestamp``; the macro itself only
    knows when it was created.

    Attributes:
        name: Human readable name (``""`` until the macro is named/saved).
        events: The events, in playback order.
        created_at: Wall-clock time (``time.time()``) when the macro was built.
    """

    name: str = ""
    events: list[KeyEvent] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    # -- container protocol -------------------------------------------------
    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self) -> Iterator[KeyEvent]:
        return iter(self.events)

    def __getitem__(self, index: int | slice) -> KeyEvent | list[KeyEvent]:
        return self.events[index]

    # -- building -----------------------------------------------------------
    def append(self, event: KeyEvent) -> KeyEvent:
        """Append ``event`` to the end of the macro and return it.

        Raises:
            TypeError: if ``event`` is not a :class:`KeyEvent`.
        """
        if not isinstance(event, KeyEvent):
            raise TypeError(f"expected a KeyEvent, got {type(event).__name__}")
        self.events.append(event)
        return event

    def extend(self, events: Iterable[KeyEvent]) -> None:
        """Append several events, preserving their order."""
        for event in events:
            self.append(event)

    def clear(self) -> None:
        """Drop every event (the macro becomes empty again)."""
        self.events.clear()

    # -- timeline -----------------------------------------------------------
    @property
    def duration(self) -> float:
        """Total playback time in seconds (sum of the event delays)."""
        return sum(event.delay for event in self.events)

    @property
    def timestamps(self) -> list[float | None]:
        """Timestamp of each event, in playback order."""
        return [event.timestamp for event in self.events]

    @property
    def timed_events(self) -> list[KeyEvent]:
        """Only the events that carry a timestamp."""
        return [event for event in self.events if event.timestamp is not None]

    @property
    def span(self) -> float:
        """Wall-clock length of the recording, in seconds.

        ``0.0`` when fewer than two events carry a timestamp.  Unlike
        :attr:`duration` this ignores delays and looks at recorded times.
        """
        times = [event.timestamp for event in self.timed_events]
        if len(times) < 2:
            return 0.0
        return max(times) - min(times)


__all__ = ["Macro"]
