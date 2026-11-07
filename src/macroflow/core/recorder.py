"""Keyboard recording.

Turns pynput listener callbacks into :class:`~macroflow.core.actions.KeyDown` /
:class:`~macroflow.core.actions.KeyUp` events appended to a
:class:`~macroflow.core.macro.Macro`, in playback order.

``pynput`` is imported lazily (and can be replaced by an injected
``listener_factory``) so the module stays importable and testable on headless
machines, where the keyboard backend cannot be initialised.

Note:
    On X11 the pynput listener thread does not always exit when
    :meth:`Recorder.stop` is called — it usually winds down on the next key
    event.  :meth:`Recorder.stop` therefore joins with a bounded timeout and
    never blocks indefinitely; the thread is a daemon and any event it still
    delivers is ignored (pynput itself also drops events after ``stop()``).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from enum import Enum
from typing import TYPE_CHECKING, Any

from macroflow.core.actions import KeyLike, key_down, key_name, key_up
from macroflow.core.macro import Macro

if TYPE_CHECKING:  # pragma: no cover - typing only
    # Annotation-only: ``from __future__ import annotations`` keeps this a
    # string, so it never needs to exist at runtime (Python 3.10 has no Self).
    from typing import Self

    from pynput.keyboard import Listener

_log = logging.getLogger(__name__)

#: Builds a pynput-like listener from ``on_press`` / ``on_release`` callbacks.
ListenerFactory = Callable[..., Any]


def _pynput_listener(**callbacks: Any) -> Listener:
    """Default factory: create a real ``pynput.keyboard.Listener``."""
    from pynput import keyboard

    return keyboard.Listener(**callbacks)


def to_keylike(key: Any) -> KeyLike | None:
    """Convert a pynput key into our :data:`~macroflow.core.actions.KeyLike`.

    Accepts ``Key`` members, single character strings and ``KeyCode`` objects
    (their ``char`` is used).  Returns ``None`` for keys that cannot be
    replayed (``KeyCode`` without a character, unknown objects).
    """
    if isinstance(key, Enum):  # pynput.keyboard.Key member
        return key
    if isinstance(key, str):
        return key if len(key) == 1 else None
    char = getattr(key, "char", None)
    if isinstance(char, str) and len(char) == 1:
        return char
    return None


class Recorder:
    """Record keyboard events into a :class:`~macroflow.core.macro.Macro`.

    Each event gets the wall-clock ``timestamp`` it happened at and a
    ``delay`` — the seconds elapsed since the previous event (for the first
    event: since :meth:`start`).  Recording is driven by a pynput listener
    thread; mutations of the macro are serialised with a lock.

    Args:
        macro: Macro to fill; a fresh one is created when omitted.
        clock: Time source, injectable for tests (defaults to ``time.time``).
        listener_factory: Replacement for the pynput listener constructor,
            used by tests to drive :meth:`_on_press` / :meth:`_on_release`.
        ignore_keys: Keys never recorded, as key names (``"f9"``) or single
            characters — typically the toggle hotkey.
        join_timeout: Seconds :meth:`stop` waits for the listener thread to
            exit before giving up on it (see the module note on X11).
    """

    def __init__(
        self,
        macro: Macro | None = None,
        *,
        clock: Callable[[], float] = time.time,
        listener_factory: ListenerFactory | None = None,
        ignore_keys: Iterable[KeyLike] = (),
        join_timeout: float = 0.5,
    ) -> None:
        self.macro = macro if macro is not None else Macro()
        self._clock = clock
        self._listener_factory = listener_factory
        self._listener: Listener | None = None
        self._lock = threading.Lock()
        self._last_time: float | None = None
        self.ignore_keys: set[str] = {key_name(key) for key in ignore_keys}
        self.join_timeout = join_timeout

    # -- state --------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        """True while the listener is capturing keys."""
        return self._listener is not None

    def ignore(self, *keys: KeyLike) -> None:
        """Never record ``keys`` (given as key members, characters or names).

        Used by :class:`~macroflow.core.hotkeys.Hotkeys` so that the toggle
        hotkey itself stays out of the recorded macro.
        """
        self.ignore_keys.update(key_name(key) for key in keys)

    def start(self) -> None:
        """Start recording (creates the listener on first call).

        Returns once the listener is actually receiving events, so no key
        pressed right after this call can be missed.

        Raises:
            RuntimeError: if recording is already in progress.
        """
        if self._listener is not None:
            raise RuntimeError("recorder is already running")
        factory = self._listener_factory or _pynput_listener
        with self._lock:
            self._last_time = self._clock()
        listener = factory(on_press=self._on_press, on_release=self._on_release)
        self._listener = listener
        try:
            listener.start()
            listener.wait()
        except BaseException:
            self._listener = None
            with self._lock:
                self._last_time = None
            raise

    def stop(self) -> Macro:
        """Stop recording and return the macro that was filled.

        The listener thread is asked to stop and given ``join_timeout``
        seconds to wind down; if it lingers (see the module note on X11) we
        move on instead of blocking — the macro is already safe, because any
        late event is ignored once recording has ended.

        Raises:
            RuntimeError: if recording is not in progress.
        """
        listener = self._listener
        if listener is None:
            raise RuntimeError("recorder is not running")
        self._listener = None
        with self._lock:
            self._last_time = None
        listener.stop()
        listener.join(timeout=self.join_timeout)
        if getattr(listener, "is_alive", lambda: False)():
            _log.debug(
                "pynput listener still alive after %.2fs stop; "
                "it is a daemon thread and its events are ignored",
                self.join_timeout,
            )
        return self.macro

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> bool:
        if self._listener is not None:
            self.stop()
        return False

    # -- listener callbacks -------------------------------------------------
    def _on_press(self, key: Any) -> None:
        """pynput ``on_press`` hook: append a :class:`KeyDown`."""
        self._record(key, key_down)

    def _on_release(self, key: Any) -> None:
        """pynput ``on_release`` hook: append a :class:`KeyUp`."""
        self._record(key, key_up)

    def _record(self, key: Any, factory: Callable[..., Any]) -> None:
        keylike = to_keylike(key)
        if keylike is None:
            return  # not replayable (e.g. a KeyCode without a character)
        if key_name(keylike) in self.ignore_keys:
            return  # the toggle hotkey, or another key we must not record
        with self._lock:
            last = self._last_time
            if last is None:
                return  # stopped between the key press and this callback
            now = self._clock()
            delay = max(0.0, now - last)  # clamp against clock jumps
            self._last_time = now
            self.macro.append(factory(keylike, delay=delay, timestamp=now))


__all__ = ["ListenerFactory", "Recorder", "to_keylike"]
