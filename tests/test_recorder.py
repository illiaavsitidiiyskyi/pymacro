# tests for keyboard recording (pynput listener is faked: CI is headless)

from enum import Enum

import pytest

from macroflow.core.actions import KeyDown, KeyUp
from macroflow.core.macro import Macro
from macroflow.core.recorder import Recorder, to_keylike


class FakeKey(Enum):
    """Stand-in for ``pynput.keyboard.Key`` (importing pynput needs a display)."""

    enter = 0xFF0D


class FakeKeyCode:
    """Stand-in for ``pynput.keyboard.KeyCode``."""

    def __init__(self, char=None, vk=0):
        self.char = char
        self.vk = vk


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class FakeListener:
    def __init__(self, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release
        self.started = False
        self.stopped = False
        self.join_timeout = None
        self.alive = True  # a listener stays "alive" until stop() + join()

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def join(self, timeout=None):
        self.join_timeout = timeout
        self.alive = False

    def is_alive(self):
        return self.alive


def make_recorder(macro=None, start=1000.0, listener_cls=FakeListener, **kwargs):
    """Build a Recorder with a fake clock and a captured fake listener."""
    clock = FakeClock(start)
    listeners = []

    def factory(**callbacks):
        listener = listener_cls(**callbacks)
        listeners.append(listener)
        return listener

    recorder = Recorder(macro, clock=clock, listener_factory=factory, **kwargs)
    return recorder, clock, listeners


def test_start_and_stop_lifecycle():
    recorder, _clock, listeners = make_recorder()

    assert not recorder.is_running
    recorder.start()
    assert recorder.is_running
    assert len(listeners) == 1
    assert listeners[0].started

    macro = recorder.stop()
    assert not recorder.is_running
    assert listeners[0].stopped and listeners[0].join_timeout == recorder.join_timeout
    assert not listeners[0].is_alive()
    assert macro is recorder.macro


def test_records_press_and_release_with_delay_and_timestamp():
    recorder, clock, listeners = make_recorder()
    recorder.start()

    clock.advance(0.5)
    listeners[0].on_press("a")  # first event: delay measured from start()
    clock.advance(0.25)
    listeners[0].on_release("a")

    assert recorder.macro.events == [
        KeyDown("a", delay=0.5, timestamp=1000.5),
        KeyUp("a", delay=0.25, timestamp=1000.75),
    ]
    assert recorder.macro.duration == pytest.approx(0.75)
    assert recorder.macro.span == pytest.approx(0.25)


def test_records_special_keys_as_key_members():
    recorder, _clock, listeners = make_recorder()
    recorder.start()

    listeners[0].on_press(FakeKey.enter)
    listeners[0].on_release(FakeKey.enter)

    assert [event.key for event in recorder.macro] == [FakeKey.enter, FakeKey.enter]


def test_records_keycode_via_its_char():
    recorder, _clock, listeners = make_recorder()
    recorder.start()

    listeners[0].on_press(FakeKeyCode(char="q"))
    listeners[0].on_release(FakeKeyCode(char="q"))

    assert [event.key for event in recorder.macro] == ["q", "q"]


def test_skips_unplayable_keys():
    recorder, _clock, listeners = make_recorder()
    recorder.start()

    listeners[0].on_press(FakeKeyCode(char=None, vk=97))  # no character
    listeners[0].on_release(object())  # unknown key object
    listeners[0].on_press("ab")  # not a single character

    assert len(recorder.macro) == 0


def test_records_into_a_given_macro():
    macro = Macro(name="existing")
    recorder, _clock, listeners = make_recorder(macro=macro)
    recorder.start()

    listeners[0].on_press("x")
    listeners[0].on_release("x")

    assert recorder.macro is macro
    assert macro.name == "existing"
    assert len(macro) == 2


def test_start_twice_raises_and_stop_when_idle_raises():
    recorder, _, _listeners = make_recorder()
    recorder.start()

    with pytest.raises(RuntimeError):
        recorder.start()

    recorder.stop()
    with pytest.raises(RuntimeError):
        recorder.stop()


def test_events_arriving_after_stop_are_ignored():
    recorder, _clock, listeners = make_recorder()
    recorder.start()
    listeners[0].on_press("a")
    recorder.stop()

    listeners[0].on_release("a")  # listener thread may still be draining
    assert len(recorder.macro) == 1
    assert isinstance(recorder.macro[0], KeyDown)


def test_delay_is_clamped_when_clock_goes_backwards():
    recorder, clock, listeners = make_recorder()
    recorder.start()

    clock.advance(0.5)
    listeners[0].on_press("a")
    clock.now -= 10.0  # NTP step / wall clock jump
    listeners[0].on_release("a")

    assert recorder.macro[1].delay == 0.0


def test_context_manager_records_and_stops():
    recorder, _clock, listeners = make_recorder()
    with recorder as active:
        assert active is recorder
        assert recorder.is_running
        listeners[0].on_press("z")
    assert not recorder.is_running
    assert len(recorder.macro) == 1


def test_stop_joins_with_the_configured_timeout():
    recorder, _clock, listeners = make_recorder(join_timeout=1.25)
    recorder.start()
    recorder.stop()
    assert listeners[0].join_timeout == 1.25
    assert not recorder.is_running


def test_stop_does_not_block_when_the_listener_lingers(caplog):
    """pynput's X11 thread can outlive stop(); we must not wait forever."""

    class LingeringListener(FakeListener):
        def join(self, timeout=None):
            self.join_timeout = timeout  # never finishes winding down

    recorder, _clock, listeners = make_recorder(listener_cls=LingeringListener)
    recorder.start()

    with caplog.at_level("DEBUG", logger="macroflow.core.recorder"):
        macro = recorder.stop()

    assert not recorder.is_running
    assert macro is recorder.macro
    assert listeners[0].join_timeout == recorder.join_timeout
    assert "daemon thread" in caplog.text


def test_to_keylike():
    assert to_keylike(FakeKey.enter) is FakeKey.enter
    assert to_keylike("a") == "a"
    assert to_keylike(FakeKeyCode(char="k")) == "k"
    assert to_keylike(FakeKeyCode(char=None)) is None
    assert to_keylike("ab") is None
    assert to_keylike(42) is None
