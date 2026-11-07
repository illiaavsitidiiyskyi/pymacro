"""KeyDown / KeyUp events.

Events are plain data objects; they never touch the keyboard themselves until
:meth:`KeyEvent.perform` is called.  ``pynput`` is imported lazily inside
``perform()`` so that this module stays importable on headless machines (CI).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pynput.keyboard import Controller, Key

#: A key is either a :class:`pynput.keyboard.Key` member (``Key.enter``) or a
#: single character string (``"a"``).
KeyLike = Union["Key", str]

#: Shared controller used when :meth:`KeyEvent.perform` is called without one.
_CONTROLLER: Controller | None = None


def _controller() -> Controller:
    """Return the process-wide keyboard controller, creating it on first use."""
    global _CONTROLLER
    if _CONTROLLER is None:
        from pynput.keyboard import Controller

        _CONTROLLER = Controller()
    return _CONTROLLER


def key_name(key: KeyLike) -> str:
    """Human readable name for ``key`` (``"enter"``, ``"a"``, ``"ctrl"``)."""
    return str(getattr(key, "name", key))


def normalize_key(key: KeyLike) -> KeyLike:
    """Validate ``key`` and return it in canonical form.

    - :class:`~pynput.keyboard.Key` members pass through untouched.
    - A string must be exactly one character (``"a"``, ``" "``).

    Raises:
        ValueError: if ``key`` is a string of the wrong length.
        TypeError: if ``key`` is neither a string nor a ``Key`` member.

    ``pynput`` is not imported here (its ``Key`` is an enum), so this works on
    headless machines where the keyboard backend cannot be initialised.
    """
    if isinstance(key, Enum):  # pynput.keyboard.Key member
        return key
    if isinstance(key, str):
        if len(key) != 1:
            raise ValueError(f"expected a single character key, got {key!r}")
        return key
    raise TypeError(f"unsupported key type: {type(key).__name__}")


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """Base class for a single key event.

    Attributes:
        key: The key affected by the event.
        delay: Seconds to wait *before* the event fires (time since the
            previous event), as recorded by the recorder.  ``0.0`` by default.
        timestamp: Wall-clock time (``time.time()``) when the event was
            recorded, or ``None`` for hand-built events.
    """

    key: KeyLike
    delay: float = 0.0
    timestamp: float | None = None

    def __str__(self) -> str:
        return f"{type(self).__name__}({key_name(self.key)}, delay={self.delay:.3f})"

    def perform(self, controller: Controller | None = None) -> None:
        """Fire the event, optionally on a specific ``controller``."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class KeyDown(KeyEvent):
    """Press ``key`` down."""

    def perform(self, controller: Controller | None = None) -> None:
        target = controller if controller is not None else _controller()
        target.press(normalize_key(self.key))


@dataclass(frozen=True, slots=True)
class KeyUp(KeyEvent):
    """Release ``key``."""

    def perform(self, controller: Controller | None = None) -> None:
        target = controller if controller is not None else _controller()
        target.release(normalize_key(self.key))


def key_down(key: KeyLike, delay: float = 0.0, timestamp: float | None = None) -> KeyDown:
    """Convenience factory for :class:`KeyDown`."""
    return KeyDown(key=normalize_key(key), delay=delay, timestamp=timestamp)


def key_up(key: KeyLike, delay: float = 0.0, timestamp: float | None = None) -> KeyUp:
    """Convenience factory for :class:`KeyUp`."""
    return KeyUp(key=normalize_key(key), delay=delay, timestamp=timestamp)


__all__ = [
    "KeyDown",
    "KeyEvent",
    "KeyLike",
    "KeyUp",
    "key_down",
    "key_name",
    "key_up",
    "normalize_key",
]
