# tests for the Macro model (ordered events + timestamps)

import time
from dataclasses import FrozenInstanceError

import pytest

from macroflow.core.actions import KeyDown, KeyUp, key_down, key_up
from macroflow.core.macro import Macro


def test_macro_starts_empty():
    macro = Macro()
    assert len(macro) == 0
    assert macro.name == ""
    assert macro.events == []
    assert macro.duration == 0.0
    assert macro.span == 0.0
    assert abs(macro.created_at - time.time()) < 1.0


def test_append_keeps_playback_order():
    macro = Macro(name="demo")
    a = macro.append(key_down("a", delay=0.1, timestamp=1000.0))
    b = macro.append(key_up("a", delay=0.2, timestamp=1000.3))

    assert macro.name == "demo"
    assert len(macro) == 2
    assert macro[0] is a
    assert macro[1] is b
    assert list(macro) == [a, b]
    assert [e.key for e in macro] == ["a", "a"]
    assert macro[:1] == [a]


def test_append_returns_the_event():
    macro = Macro()
    event = KeyDown("b")
    assert macro.append(event) is event


def test_append_rejects_non_events():
    macro = Macro()
    with pytest.raises(TypeError):
        macro.append("a")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        macro.append(42)  # type: ignore[arg-type]
    assert len(macro) == 0


def test_extend_and_clear():
    macro = Macro()
    macro.extend([key_down("x"), key_up("x")])
    assert len(macro) == 2
    macro.clear()
    assert len(macro) == 0
    assert macro.events == []


def test_duration_sums_delays():
    macro = Macro()
    macro.extend(
        [
            key_down("a", delay=0.1),
            key_up("a", delay=0.25),
            key_down("b", delay=1.5),
        ]
    )
    assert macro.duration == pytest.approx(1.85)
    assert Macro().duration == 0.0


def test_timestamps_and_timed_events():
    macro = Macro()
    macro.append(key_down("a", timestamp=100.0))
    macro.append(key_up("a"))  # hand-built event: no timestamp

    assert macro.timestamps == [100.0, None]
    assert [e.key for e in macro.timed_events] == ["a"]


def test_span_uses_recorded_times():
    macro = Macro()
    assert macro.span == 0.0

    macro.append(key_down("a", delay=0.1, timestamp=1000.0))
    assert macro.span == 0.0  # only one timestamp

    macro.append(key_up("a", delay=0.4, timestamp=1001.5))
    macro.append(key_down("b", delay=9.0, timestamp=1002.0))
    assert macro.span == pytest.approx(2.0)  # 1002.0 - 1000.0, not 9.5s of delays


def test_hand_built_events_have_no_timestamp():
    event = KeyDown("z")
    assert event.timestamp is None
    assert KeyUp("z", timestamp=5.0).timestamp == 5.0


def test_events_are_immutable_and_value_like():
    macro = Macro()
    macro.append(key_down("a", timestamp=1.0))
    with pytest.raises(FrozenInstanceError):
        macro[0].delay = 9.9  # type: ignore[index]
