# tests for KeyDown / KeyUp events

from dataclasses import FrozenInstanceError
from enum import Enum

import pytest

from macroflow.core.actions import (
    KeyDown,
    KeyEvent,
    KeyUp,
    key_down,
    key_name,
    key_up,
    normalize_key,
)


class FakeKey(Enum):
    enter = 0xFF0D


class FakeController:
    def __init__(self):
        self.log = []

    def press(self, key):
        self.log.append(("press", key))

    def release(self, key):
        self.log.append(("release", key))


def test_keydown_presses_and_keyup_releases():
    controller = FakeController()
    key_down(FakeKey.enter, delay=0.5).perform(controller)
    key_up("a").perform(controller)
    assert controller.log == [("press", FakeKey.enter), ("release", "a")]


def test_events_are_immutable_value_objects():
    assert KeyDown(FakeKey.enter) == KeyDown(FakeKey.enter)
    assert KeyDown(FakeKey.enter) != KeyUp(FakeKey.enter)
    with pytest.raises(FrozenInstanceError):
        KeyDown(FakeKey.enter).key = "b"  # type: ignore[misc]


def test_default_delay_is_zero():
    assert KeyUp("a").delay == 0.0
    assert KeyDown("a", delay=0.25).delay == 0.25


def test_normalize_key():
    assert normalize_key(" ") == " "
    assert normalize_key(FakeKey.enter) is FakeKey.enter
    with pytest.raises(ValueError):
        normalize_key("ab")
    with pytest.raises(TypeError):
        normalize_key(5)  # type: ignore[arg-type]


def test_key_name_and_str():
    assert key_name(FakeKey.enter) == "enter"
    assert key_name("z") == "z"
    assert str(KeyDown("a", delay=0.1)) == "KeyDown(a, delay=0.100)"
    assert str(KeyUp(FakeKey.enter)) == "KeyUp(enter, delay=0.000)"


def test_base_class_is_abstract():
    with pytest.raises(NotImplementedError):
        KeyEvent("a").perform(FakeController())  # type: ignore[arg-type]
