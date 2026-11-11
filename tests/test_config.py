# tests for the configuration knobs

import math

import pytest

from macroflow.core import optimizer
from macroflow.utils.config import DEFAULT_MIN_DELAY


def test_default_min_delay_is_two_milliseconds():
    assert DEFAULT_MIN_DELAY == pytest.approx(0.002)


def test_default_min_delay_is_a_usable_delay():
    assert isinstance(DEFAULT_MIN_DELAY, float)
    assert math.isfinite(DEFAULT_MIN_DELAY)
    assert DEFAULT_MIN_DELAY >= 0.0


def test_optimizer_uses_the_configured_default():
    # guards against the two modules drifting apart after a config change
    assert optimizer.DEFAULT_MIN_DELAY == DEFAULT_MIN_DELAY
