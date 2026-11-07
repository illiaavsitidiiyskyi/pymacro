# tests for the F9 toggle hotkey (pynput listener is faked: CI is headless)

from enum import Enum

import pytest

from macroflow.core.actions import KeyDown
from macroflow.core.hotkeys import Hotkeys
from macroflow.core.recorder import Recorder


class FakeKey(Enum):
    """Stand-in for ``pynput.keyboard.Key``."""

    f9 = 0xFFC6
    f10 = 0xFFC7


class FakeKeyCode:
    def __init__(self, char=None):
        self.char = char


class FakeListener:
    def __init__(self, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release
        self.started = False
        self.join_timeout = None
        self.alive = True

    def start(self):
        self.started = True

    def wait(self):
        self.waited = True

    def stop(self):
        self.alive = False

    def join(self, timeout=None):
        self.join_timeout = timeout

    def is_alive(self):
        return self.alive


def make(key=None, on_recorded=None, **kwargs):
    """Build a Hotkeys wired to a real Recorder, both with fake listeners."""
    recorder_listeners = []
    hotkey_listeners = []

    def recorder_factory(**callbacks):
        listener = FakeListener(**callbacks)
        recorder_listeners.append(listener)
        return listener

    def hotkey_factory(**callbacks):
        listener = FakeListener(**callbacks)
        hotkey_listeners.append(listener)
        return listener

    recorder = Recorder(listener_factory=recorder_factory)
    hotkeys = Hotkeys(
        recorder,
        on_recorded=on_recorded,
        listener_factory=hotkey_factory,
        **({"key": key} if key is not None else {}),
        **kwargs,
    )
    return hotkeys, recorder, hotkey_listeners, recorder_listeners


def test_f9_press_starts_recording():
    hotkeys, recorder, hotkey_listeners, _ = make()

    hotkeys.start()
    assert hotkeys.is_running and hotkey_listeners[0].started
    assert hotkey_listeners[0].waited  # ready before start() returns
    assert not recorder.is_running

    hotkey_listeners[0].on_press(FakeKey.f9)
    assert recorder.is_running


def test_toggle_key_never_lands_in_the_macro():
    """F9 starts/stops recording but must not be recorded itself."""
    hotkeys, recorder, hotkey_listeners, recorder_listeners = make()
    hotkeys.start()
    assert "f9" in recorder.ignore_keys

    hotkey_listeners[0].on_press(FakeKey.f9)  # toggle on

    # the recorder's own listener sees the toggle key's release plus real keys
    recorder_listeners[0].on_press(FakeKey.f9)
    recorder_listeners[0].on_release(FakeKey.f9)
    recorder_listeners[0].on_press("a")
    recorder_listeners[0].on_release("a")

    hotkey_listeners[0].on_release(FakeKey.f9)
    hotkey_listeners[0].on_press(FakeKey.f9)  # toggle off

    assert [event.key for event in recorder.macro] == ["a", "a"]


def test_next_f9_press_stops_and_dispatches_the_macro():
    recorded = []
    hotkeys, recorder, hotkey_listeners, recorder_listeners = make(
        on_recorded=recorded.append
    )
    hotkeys.start()

    hotkey_listeners[0].on_press(FakeKey.f9)  # start
    recorder_listeners[0].on_press("a")  # user types while recording
    hotkey_listeners[0].on_release(FakeKey.f9)
    hotkey_listeners[0].on_press(FakeKey.f9)  # stop

    assert not recorder.is_running
    assert len(recorded) == 1
    assert len(recorded[0]) == 1
    assert isinstance(recorded[0][0], KeyDown)


def test_key_auto_repeat_does_not_re_toggle():
    hotkeys, recorder, hotkey_listeners, _ = make()
    hotkeys.start()

    hotkey_listeners[0].on_press(FakeKey.f9)
    hotkey_listeners[0].on_press(FakeKey.f9)  # auto-repeat while held
    hotkey_listeners[0].on_press(FakeKey.f9)
    assert recorder.is_running  # still recording: one press, one toggle

    hotkey_listeners[0].on_release(FakeKey.f9)
    hotkey_listeners[0].on_press(FakeKey.f9)
    assert not recorder.is_running


def test_other_keys_do_not_toggle():
    hotkeys, recorder, hotkey_listeners, _ = make()
    hotkeys.start()

    hotkey_listeners[0].on_press(FakeKey.f10)
    hotkey_listeners[0].on_release(FakeKey.f10)
    assert not recorder.is_running


def test_toggle_key_can_be_a_single_character():
    hotkeys, recorder, hotkey_listeners, _ = make(key="q")
    hotkeys.start()

    hotkey_listeners[0].on_press(FakeKeyCode(char="q"))
    assert recorder.is_running
    hotkey_listeners[0].on_release(FakeKeyCode(char="q"))
    hotkey_listeners[0].on_press(FakeKeyCode(char="q"))
    assert not recorder.is_running


def test_toggle_key_defaults_to_f9_by_name():
    """The default matches ``Key.f9`` by name, without importing pynput."""
    hotkeys, _, hotkey_listeners, _ = make()
    assert hotkeys.key == "f9"

    hotkeys.start()
    hotkey_listeners[0].on_press(FakeKey.f9)
    assert hotkeys.recorder.is_running


def test_callback_failure_is_logged_not_raised(caplog):
    def explode(_macro):
        raise ValueError("no disk")

    hotkeys, recorder, hotkey_listeners, _ = make(on_recorded=explode)
    hotkeys.start()

    hotkey_listeners[0].on_press(FakeKey.f9)
    with caplog.at_level("ERROR", logger="macroflow.core.hotkeys"):
        hotkey_listeners[0].on_release(FakeKey.f9)
        hotkey_listeners[0].on_press(FakeKey.f9)  # must not raise

    assert not recorder.is_running
    assert "on_recorded callback failed" in caplog.text
    assert hotkeys.is_running  # listener survives the bad callback


def test_toggle_works_without_a_listener():
    recorded = []
    hotkeys, recorder, _, _ = make(on_recorded=recorded.append)

    hotkeys.toggle()
    assert recorder.is_running and not hotkeys.is_running

    hotkeys.toggle()
    assert not recorder.is_running
    assert len(recorded) == 1


def test_start_twice_raises_and_stop_when_idle_raises():
    hotkeys, _, _, _ = make()
    hotkeys.start()
    with pytest.raises(RuntimeError):
        hotkeys.start()
    hotkeys.stop()
    with pytest.raises(RuntimeError):
        hotkeys.stop()


def test_stop_joins_with_the_configured_timeout():
    hotkeys, _, hotkey_listeners, _ = make(join_timeout=1.5)
    hotkeys.start()
    hotkeys.stop()
    assert hotkey_listeners[0].join_timeout == 1.5
    assert not hotkeys.is_running


def test_context_manager():
    hotkeys, recorder, hotkey_listeners, _ = make()
    with hotkeys as active:
        assert active is hotkeys and hotkeys.is_running
        hotkey_listeners[0].on_press(FakeKey.f9)
        assert recorder.is_running
    assert not hotkeys.is_running
