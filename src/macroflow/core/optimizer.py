"""Delay optimization: overwrite every delay with a minimum value.

Recorded macros carry the wall-clock gaps between key events, which makes them
slow to replay (and prone to replaying too slowly for the target app).  This
module rewrites all of them to a single minimum delay so the macro runs at a
constant, predictable pace.

Events are frozen dataclasses, so delays are never mutated in place: each event
is rebuilt with :func:`dataclasses.replace`, leaving keys and timestamps
untouched.  The rewrite is strictly one-for-one — no event is dropped, added
or moved — so the key order and the press/release pairs come out exactly as
they went in (check with :func:`pairs_intact`).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import replace

from macroflow.core.actions import KeyDown, KeyLike, KeyUp, key_name
from macroflow.core.macro import Macro

# Re-exported for backwards compatibility: the knob itself lives in config.
from macroflow.utils.config import DEFAULT_MIN_DELAY

__all__ = ["DEFAULT_MIN_DELAY", "iter_pairs", "optimize", "pairs_intact"]


def _check_min_delay(min_delay: float) -> float:
    """Validate ``min_delay`` and return it as a ``float``.

    Raises:
        TypeError: if it is not a real number (``bool`` counts as not one).
        ValueError: if it is negative or not finite (``nan`` / ``inf``).
    """
    if isinstance(min_delay, bool) or not isinstance(min_delay, (int, float)):
        raise TypeError(f"min_delay must be a number, got {type(min_delay).__name__}")
    value = float(min_delay)
    if not math.isfinite(value):
        raise ValueError(f"min_delay must be finite, got {value!r}")
    if value < 0.0:
        raise ValueError(f"min_delay must be >= 0, got {value!r}")
    return value


def optimize(macro: Macro, min_delay: float = DEFAULT_MIN_DELAY, *, inplace: bool = False) -> Macro:
    """Overwrite every event delay in ``macro`` with ``min_delay``.

    The order of the events, their keys and their timestamps are preserved;
    only ``delay`` changes, so :attr:`~macroflow.core.macro.Macro.duration`
    becomes ``len(macro) * min_delay``.  Events are rebuilt one-for-one in
    playback order, so a macro whose press/release pairs are intact stays
    intact (:func:`pairs_intact` is true for the output whenever it is true
    for the input); ``optimize`` never validates or repairs the pairing
    itself.

    Args:
        macro: The macro whose delays should be rewritten.
        min_delay: Seconds to write into every event.  Defaults to
            :data:`macroflow.utils.config.DEFAULT_MIN_DELAY` (2 ms).
        inplace: When ``True`` rewrite ``macro`` itself and return it; when
            ``False`` (the default) leave ``macro`` untouched and return a
            copy.

    Returns:
        The optimized macro: ``macro`` itself when ``inplace=True``,
        otherwise a new :class:`~macroflow.core.macro.Macro` with the same
        name and ``created_at``.

    Raises:
        TypeError: if ``macro`` is not a :class:`Macro` or ``min_delay`` is
            not a number.
        ValueError: if ``min_delay`` is negative or not finite.
    """
    if not isinstance(macro, Macro):
        raise TypeError(f"expected a Macro, got {type(macro).__name__}")
    delay = _check_min_delay(min_delay)

    optimized = [replace(event, delay=delay) for event in macro.events]
    if inplace:
        macro.events = optimized
        return macro
    return replace(macro, events=optimized)


def iter_pairs(macro: Macro) -> Iterator[tuple[KeyDown, KeyUp]]:
    """Yield every ``(press, release)`` pair, ordered by their press.

    A pair is a :class:`~macroflow.core.actions.KeyDown` and the
    :class:`~macroflow.core.actions.KeyUp` of the same key that closes it.
    Different keys may interleave (``down a, down b, up a, up b`` — that is a
    chord), but a key may not be pressed again before its previous press was
    released, and a release always needs a matching earlier press.  Events
    that are neither ``KeyDown`` nor ``KeyUp`` are ignored.

    Returns:
        An iterator over the pairs as they appear in :attr:`Macro.events`.

    Raises:
        TypeError: if ``macro`` is not a :class:`Macro`.
        ValueError: if the pairs are not intact (see :func:`pairs_intact`).
    """
    if not isinstance(macro, Macro):
        raise TypeError(f"expected a Macro, got {type(macro).__name__}")
    waiting: dict[KeyLike, KeyDown] = {}
    finished: list[tuple[int, KeyDown, KeyUp]] = []  # (press index, press, release)
    for index, event in enumerate(macro.events):
        if isinstance(event, KeyDown):
            if event.key in waiting:
                raise ValueError(f"key {key_name(event.key)!r} pressed again before release")
            waiting[event.key] = event
        elif isinstance(event, KeyUp):
            down = waiting.pop(event.key, None)
            if down is None:
                raise ValueError(f"key {key_name(event.key)!r} released without a press")
            finished.append((index, down, event))
    if waiting:
        dangling = next(iter(waiting))
        raise ValueError(f"key {key_name(dangling)!r} pressed but never released")
    finished.sort(key=lambda item: item[0])  # chords come out in press order
    return iter([(down, up) for _, down, up in finished])


def pairs_intact(macro: Macro) -> bool:
    """True when every press in ``macro`` is matched by exactly one release.

    The pairing is checked per key: its events must alternate press/release,
    starting with a press and ending with a release.  Keys may interleave
    across each other (chords).  Events that are neither ``KeyDown`` nor
    ``KeyUp`` are ignored.

    Raises:
        TypeError: if ``macro`` is not a :class:`Macro`.
    """
    if not isinstance(macro, Macro):
        raise TypeError(f"expected a Macro, got {type(macro).__name__}")
    try:
        iter_pairs(macro)
    except ValueError:
        return False
    return True
