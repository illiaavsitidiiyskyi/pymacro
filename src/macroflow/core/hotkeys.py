"""Global hotkeys.

F9 toggles recording: the first press starts it, the next press stops it and
hands the finished :class:`~macroflow.core.macro.Macro` to the optional
``on_recorded`` callback.  Other hotkeys (play, stop) are TODO.

Like :mod:`~macroflow.core.recorder` this module imports ``pynput`` lazily and
accepts an injected ``listener_factory``, so it stays importable and testable
on headless machines.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from macroflow.core.actions import key_name
from macroflow.core.macro import Macro
from macroflow.core.recorder import ListenerFactory, Recorder, to_keylike

if TYPE_CHECKING:  # pragma: no cover - typing only
    # Annotation-only: ``from __future__ import annotations`` keeps this a
    # string, so it never needs to exist at runtime (Python 3.10 has no Self).
    from typing import Self

    from pynput.keyboard import Listener

_log = logging.getLogger(__name__)

#: Default toggle key, matched by name against ``pynput.keyboard.Key.f9``.
DEFAULT_TOGGLE_KEY = "f9"

#: Called with the macro when recording is toggled off.
RecordedCallback = Callable[[Macro], None]


def _pynput_listener(**callbacks: Any) -> Listener:
    """Default factory: create a real ``pynput.keyboard.Listener``."""
    from pynput import keyboard

    return keyboard.Listener(**callbacks)


class Hotkeys:
    """Global hotkey listener: F9 toggles :class:`Recorder` on and off.

    Args:
        recorder: Recorder whose recording session is toggled.
        on_recorded: Called with the macro every time recording stops.  An
            exception raised here is logged, never propagated — pynput stops
            the whole listener when a callback blows up.
        key: Toggle key: a :class:`~pynput.keyboard.Key` member, a single
            character, or a key *name* such as ``"f9"`` (matched by name, so
            the default needs no pynput import).  Defaults to ``"f9"``.
        listener_factory: Replacement for the pynput listener constructor,
            used by tests to drive :meth:`_on_press` / :meth:`_on_release`.
        join_timeout: Seconds :meth:`stop` waits for the listener thread to
            wind down (pynput's X11 thread may linger; see ``recorder``).
    """

    def __init__(
        self,
        recorder: Recorder,
        *,
        on_recorded: RecordedCallback | None = None,
        key: Any = DEFAULT_TOGGLE_KEY,
        listener_factory: ListenerFactory | None = None,
        join_timeout: float = 0.5,
    ) -> None:
        self.recorder = recorder
        self.on_recorded = on_recorded
        self.key = key
        self.join_timeout = join_timeout
        self._listener_factory = listener_factory
        self._listener: Listener | None = None
        self._key_down = False

    # -- state --------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        """True while the hotkey listener is up (not: while recording)."""
        return self._listener is not None

    def start(self) -> None:
        """Start listening for the hotkeys.

        Raises:
            RuntimeError: if the listener is already up.
        """
        if self._listener is not None:
            raise RuntimeError("hotkeys are already running")
        self.recorder.ignore(self.key)  # the toggle key never lands in a macro
        factory = self._listener_factory or _pynput_listener
        listener = factory(on_press=self._on_press, on_release=self._on_release)
        self._listener = listener
        try:
            listener.start()
            listener.wait()  # ready to receive events before we return
        except BaseException:
            self._listener = None
            raise

    def stop(self) -> None:
        """Stop listening for hotkeys (recording itself is left alone).

        Joins the listener thread for at most ``join_timeout`` seconds; a
        lingering thread (see the note in :mod:`macroflow.core.recorder`) is
        logged at debug level and dropped instead of blocking.

        Raises:
            RuntimeError: if the listener is not up.
        """
        listener = self._listener
        if listener is None:
            raise RuntimeError("hotkeys are not running")
        self._listener = None
        self._key_down = False
        listener.stop()
        listener.join(timeout=self.join_timeout)
        if getattr(listener, "is_alive", lambda: False)():
            _log.debug(
                "pynput hotkey listener still alive after %.2fs stop; "
                "it is a daemon thread and its events are ignored",
                self.join_timeout,
            )

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> bool:
        if self._listener is not None:
            self.stop()
        return False

    # -- toggle -------------------------------------------------------------
    def toggle(self) -> None:
        """Start recording when idle, otherwise stop and dispatch the macro."""
        if self.recorder.is_running:
            macro = self.recorder.stop()
            _log.info("recording stopped (%d events)", len(macro))
            if self.on_recorded is not None:
                try:
                    self.on_recorded(macro)
                except Exception:  # noqa: BLE001 - user code must not kill pynput
                    _log.exception("on_recorded callback failed")
        else:
            self.recorder.start()
            _log.info("recording started (press %s again to stop)", key_name(self.key))

    # -- listener callbacks -------------------------------------------------
    def _on_press(self, key: Any) -> None:
        """pynput ``on_press`` hook: the toggle key starts/stops recording."""
        if self._matches(key) and not self._key_down:
            self._key_down = True  # ignores key auto-repeat while held
            self.toggle()

    def _on_release(self, key: Any) -> None:
        """pynput ``on_release`` hook: re-arms the toggle key."""
        if self._matches(key):
            self._key_down = False

    def _matches(self, key: Any) -> bool:
        """True if the pynput ``key`` is the configured toggle key."""
        wanted = self.key
        if wanted is None:
            return False
        if isinstance(wanted, str) and len(wanted) != 1:
            return key_name(key) == wanted  # e.g. "f9" vs Key.f9
        return to_keylike(key) == wanted


__all__ = ["DEFAULT_TOGGLE_KEY", "Hotkeys", "RecordedCallback"]
