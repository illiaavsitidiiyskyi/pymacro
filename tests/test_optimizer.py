# tests for delay optimization (overwrite every delay with a minimum value)

import math
from dataclasses import FrozenInstanceError

import pytest

from macroflow.core.actions import KeyDown, KeyEvent, KeyUp, key_down, key_up
from macroflow.core.macro import Macro
from macroflow.core.optimizer import DEFAULT_MIN_DELAY, iter_pairs, optimize, pairs_intact
from macroflow.utils.config import DEFAULT_MIN_DELAY as CONFIG_DEFAULT_MIN_DELAY


def build_macro() -> Macro:
    """A small recording: two keys with wildly different recorded delays.

    The press on ``b`` is deliberately dangling (never released) — see
    :func:`macroflow.core.optimizer.pairs_intact`.
    """
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


def test_default_comes_from_config():
    assert DEFAULT_MIN_DELAY == CONFIG_DEFAULT_MIN_DELAY == pytest.approx(0.002)


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


# -- key order and press/release pairs ---------------------------------------


def build_chords() -> Macro:
    """A balanced recording with an interleaved chord, then a repeat press."""
    macro = Macro(name="chords")
    macro.extend(
        [
            key_down("a", delay=0.5, timestamp=1000.0),
            key_down("b", delay=0.2, timestamp=1000.5),
            key_up("a", delay=0.1, timestamp=1000.7),
            key_up("b", delay=0.3, timestamp=1001.0),
            key_down("a", delay=0.4, timestamp=1001.4),
            key_up("a", delay=0.05, timestamp=1001.8),
        ]
    )
    return macro


def structure(macro: Macro) -> list[tuple[type, object]]:
    """Every property of the events except their delays."""
    return [(type(event), event.key) for event in macro]


def test_key_order_is_preserved_exactly():
    original = build_chords()
    optimized = optimize(original)

    assert len(optimized) == len(original)
    assert structure(optimized) == structure(original)
    assert [event.key for event in optimized] == ["a", "b", "a", "b", "a", "a"]
    assert optimized.timestamps == original.timestamps


def test_press_release_pairs_stay_intact():
    original = build_chords()
    assert pairs_intact(original)

    optimized = optimize(original)

    assert pairs_intact(optimized)
    assert [(down.key, up.key) for down, up in iter_pairs(optimized)] == [
        ("a", "a"),
        ("b", "b"),
        ("a", "a"),
    ]


def test_pairs_keep_their_playback_positions():
    original = build_chords()
    optimized = optimize(original)

    def pair_shape(macro: Macro) -> list[tuple[type, object, type, object]]:
        return [(type(d), d.key, type(u), u.key) for d, u in iter_pairs(macro)]

    def press_release_indices(macro: Macro) -> tuple[list[int], list[int]]:
        downs = [i for i, e in enumerate(macro) if isinstance(e, KeyDown)]
        ups = [i for i, e in enumerate(macro) if isinstance(e, KeyUp)]
        return downs, ups

    assert pair_shape(optimized) == pair_shape(original)
    assert press_release_indices(optimized) == press_release_indices(original)
    # the yielded pairs are the very events stored in the macro
    down_a, up_a = next(iter(iter_pairs(optimized)))
    assert down_a is optimized[0]
    assert up_a is optimized[2]


def test_optimize_neither_fixes_nor_breaks_pairing():
    broken = build_macro()  # dangling press on "b"
    assert not pairs_intact(broken)

    assert not pairs_intact(optimize(broken))


def test_dangling_press_is_not_intact():
    with pytest.raises(ValueError, match="never released"):
        iter_pairs(build_macro())


def test_stray_release_is_not_intact():
    macro = Macro()
    macro.append(key_up("a"))

    assert not pairs_intact(macro)
    with pytest.raises(ValueError, match="without a press"):
        iter_pairs(macro)


def test_double_press_is_not_intact():
    macro = Macro()
    macro.extend([key_down("a"), key_down("a"), key_up("a"), key_up("a")])

    assert not pairs_intact(macro)
    with pytest.raises(ValueError, match="before release"):
        iter_pairs(macro)


def test_empty_macro_pairs_are_intact():
    assert pairs_intact(Macro())
    assert list(iter_pairs(Macro())) == []


def test_pair_checks_ignore_other_events():
    macro = Macro()
    macro.extend([key_down("a"), KeyEvent("z"), key_up("a")])

    assert pairs_intact(macro)
    assert len(list(iter_pairs(macro))) == 1


def test_pair_checks_reject_non_macro():
    with pytest.raises(TypeError, match="Macro"):
        pairs_intact([])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Macro"):
        iter_pairs([])  # type: ignore[arg-type]
