# tests for the CLI entry point (python -m macroflow / `macroflow` script)

import pytest

from macroflow.__main__ import main


def test_main_returns_zero(capsys):
    assert main([]) == 0
    assert "macroflow" in capsys.readouterr().out


def test_main_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "macroflow 0.1.0" in capsys.readouterr().out
