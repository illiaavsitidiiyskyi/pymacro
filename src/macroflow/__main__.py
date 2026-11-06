"""Entry point: ``python -m macroflow`` (and the ``macroflow`` script)."""

from __future__ import annotations

import argparse
import sys

from macroflow import __version__


def main(argv: list[str] | None = None) -> int:
    """Run the macroflow CLI.

    TODO: subcommands — record / play / optimize / list (see docs/usage.md).
    """
    parser = argparse.ArgumentParser(prog="macroflow", description=__doc__)
    parser.add_argument("--version", action="version", version=f"macroflow {__version__}")
    parser.parse_args(argv)

    print(f"macroflow {__version__} — nothing to do yet (WIP)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
