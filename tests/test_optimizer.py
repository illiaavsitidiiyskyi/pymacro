# tests for delay optimization (overwrite every delay with a minimum value)

import math
from dataclasses import FrozenInstanceError

import pytest

from macroflow.core.actions import KeyDown, key_down, key_up
from macroflow.core.macro import Macro
from macroflow.core.optimizer import DEFAULT_MIN_DELAY, optimize


def build_macro() -> Macro:
    """A small recording: two keys with wildly different recorded delays."""
    macro = Macro(name="demo", created_at=1234.0)
    macro.extend(
        [
            key_down("a", delay=1.5, timestamp=1000.0),
            key_up("a", delay=0.0, timestamp=1001.5),
            key_down("b", delay=0.42, timestamp=1001.6),
        ]
    )
    return macro


def test_all_delays_are_overwritten_with_the_default():
    macro = build_macro()
    optimized = optimize(macro)

    assert [event.delay for event in optimized] == [DEFAULT_MIN_DELAY] * 3
    assert optimized.duration == pytest.approx(3 * DEFAULT_MIN_DELAY)


def test_all_delays_are_overwritten_with_a_custom_value():
    optimized = optimize(build_macro(), 0.05)

    assert [event.delay for event in optimized] == [0.05, 0.05, 0.05]
    assert optimized.duration == pytest.approx(0.15)


def test_zero_min_delay_strips_delays():
    optimized = optimize(build_macro(), 0)
    assert [event.delay for event in optimized] == [0.0, 0.0, 0.0]


def test_returns_a_copy_and_leaves_the_original_alone():
    macro = build_macro()
    optimized = optimize(macro, 0.01)

    assert optimized is not macro
    assert optimized.events is not macro.events
    assert [event.delay for event in macro] == [1.5, 0.0, 0.42]
    # events are frozen, so the rewrite must not touch the recorded objects
    assert macro.events[0] is not optimized.events[0]
    with pytest.raises(FrozenInstanceError):
        optimized[0].delay = 9.9  # type: ignore[index]


def test_inplace_rewrites_and_returns_the_same_macro():
    macro = build_macro()
    optimized = optimize(macro, 0.2, inplace=True)

    assert optimized is macro
    assert [event.delay for event in macro] == [0.2, 0.2, 0.2]


def test_keys_order_and_timestamps_are_preserved():
    original = build_macro()
    optimized = optimize(original, 0.01)

    assert type(optimized[0]) is KeyDown  # event classes survive the rewrite
    assert [event.key for event in optimized] == [event.key for event in original]
    assert [type(event) for event in optimized] == [type(event) for event in original]
    assert optimized.timestamps == [1000.0, 1001.5, 1001.6]
    assert optimized.span == pytest.approx(original.span)


def test_name_and_created_at_are_preserved():
    optimized = optimize(build_macro())

    assert optimized.name == "demo"
    assert optimized.created_at == 1234.0


def test_empty_macro_is_a_no_op():
    optimized = optimize(Macro())

    assert len(optimized) == 0
    assert optimized.duration == 0.0


def test_rejects_negative_min_delay():
    with pytest.raises(ValueError, match="min_delay"):
        optimize(build_macro(), -0.1)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_rejects_non_finite_min_delay(bad):
    with pytest.raises(ValueError, match="min_delay"):
        optimize(build_macro(), bad)


@pytest.mark.parametrize("bad", ["0.1", None, True])
def test_rejects_non_numeric_min_delay(bad):
    with pytest.raises(TypeError, match="min_delay"):
        optimize(build_macro(), bad)  # type: ignore[arg-type]


def test_rejects_non_macro():
    with pytest.raises(TypeError, match="Macro"):
        optimize([key_up("a")])  # type: ignore[arg-type]
