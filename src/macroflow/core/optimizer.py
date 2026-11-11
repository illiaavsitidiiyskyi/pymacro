"""Delay optimization: overwrite every delay with a minimum value.

Recorded macros carry the wall-clock gaps between key events, which makes them
slow to replay (and prone to replaying too slowly for the target app).  This
module rewrites all of them to a single minimum delay so the macro runs at a
constant, predictable pace.

Events are frozen dataclasses, so delays are never mutated in place: each event
is rebuilt with :func:`dataclasses.replace`, leaving keys and timestamps
untouched.
"""

from __future__ import annotations

import math
from dataclasses import replace

from macroflow.core.macro import Macro

#: Default minimum delay, in seconds (10 ms).  Raise it if the target
#: application drops keys that arrive this fast.
DEFAULT_MIN_DELAY = 0.01

__all__ = ["DEFAULT_MIN_DELAY", "optimize"]


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
    becomes ``len(macro) * min_delay``.

    Args:
        macro: The macro whose delays should be rewritten.
        min_delay: Seconds to write into every event.  Defaults to
            :data:`DEFAULT_MIN_DELAY`.
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
