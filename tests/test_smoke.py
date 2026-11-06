# smoke test: package must be importable after `pip install -e .`

import macroflow


def test_import_macroflow():
    assert macroflow is not None
