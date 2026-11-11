"""Configuration: hotkeys, min delay value.

Single home for the project's tunables — change the values here once and
every caller picks them up.
"""

from __future__ import annotations

#: Minimum delay written into every event by
#: :func:`macroflow.core.optimizer.optimize`, in seconds (2 ms).  Raise it if
#: the target application drops keys that arrive this fast.
DEFAULT_MIN_DELAY = 0.002

__all__ = ["DEFAULT_MIN_DELAY"]
