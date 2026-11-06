"""macroflow — a keyboard macro recorder.

Layout:
    core/    recorder, player, macro model, actions, hotkeys, optimizer, storage
    ui/      tray and main window (optional, later)
    utils/   config, logging, timing helpers

Entry points: ``python -m macroflow`` or the ``macroflow`` console script.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
