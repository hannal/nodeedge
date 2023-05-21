from __future__ import annotations

import dataclasses
from typing import Union
from unittest.mock import MagicMock

import pytest

from nodeedge.constants import EnumOperand
from nodeedge.mixins import (
    Cloneable,
    Valueable,
    Composition,
    CompositableItem,
    CompositionListener,
)


def test_cloneable():
    class Sample(Cloneable):
        __cloning_attrs = frozenset(["name2"])

        value: int
        value2: int
        value3: int
        name: Union[str, None] = None
        name2: str = "hello"

        def __init__(self, value: int, /, value2: int, *, value3: int = 0) -> None:
            self.value = value
            self.value2 = value2
            self.value3 = value3

        def set_name(self, value: Union[str, None]):
            return self._clone(attrs={"name": value})

    origin = Sample(10, 20)
    assert origin._Cloneable__init_args == ("value", "value2")
    assert origin._Cloneable__init_kwargs == frozenset(["value3"])
    assert origin.value == 10
    assert origin.value2 == 20
    assert origin.value3 == 0
    assert origin.name is None
    assert origin.name2 == Sample.name2

    obj = origin.set_name("test")
    assert origin is not obj
    assert origin.value == obj.value
    assert origin.value2 == obj.value2
    assert origin.name != obj.name
    assert origin.name2 == obj.name2


def test_valueable():
    class Sample(Valueable[int]):
        pass

    with pytest.raises(TypeError):
        Sample("hello")

    origin = Sample(10)
    assert origin.value == 10

    obj = origin.set_value(20)
    assert origin is not obj
    assert origin.value != obj.value
    assert obj.value == 20

    obj2 = -obj
    assert obj is not obj2
    assert obj.value == 20
    assert obj2.value == -20

    obj3 = -obj2
    assert obj2 is not obj3
    assert obj3.value == 20
    assert obj2.value == -20


def test_composite():
    class CompositedItem(Composition):
        pass

    @dataclasses.dataclass(frozen=True)
    class Item(CompositableItem[dict, CompositedItem]):
        name: str

    item1 = Item("hello")
    item2 = Item("world")
    composited = item1 & item2
    assert isinstance(composited, CompositedItem)


@pytest.fixture
def composition_listener():
    mock = MagicMock()
    queries = []

    def on_composite(item, operand, direction, depth):
        mock.on_composite()
        if item and operand:
            queries.append(item)
        elif item and not operand:
            queries.append(item)
        elif not item and operand:
            queries.append(operand)
        return None

    def on_begin_wrap(depth, item):
        mock.on_begin_wrap()
        queries.append("(")
        return None

    def on_finish_wrap(depth, item):
        mock.on_finish_wrap()
        queries.append(")")
        return

    listener = CompositionListener(
        on_composite=on_composite,
        on_begin_wrap=on_begin_wrap,
        on_finish_wrap=on_finish_wrap,
    )
    return listener, mock, queries


def test_simple_composition_map(composition_listener):
    listener, mock, queries = composition_listener

    class CompositedItem(Composition):
        _listener = listener

        def on_composite(self, depth=0, direction=""):
            return f"composited<{depth}, {direction}>"

    @dataclasses.dataclass(frozen=True)
    class Item(CompositableItem[str, CompositedItem]):
        name: str

        def on_composite(self, depth=0, direction=""):
            return f"item<{self.name}, {depth}, {direction}>"

    item1 = Item("hello")
    item2 = Item("world")
    composited = item1 & item2
    composited.map()

    # fmt: off
    expected = [
        "(",
            item1,
            EnumOperand.AND,
            item2,
        ")",
    ]
    # fmt: on

    mock.on_composite.assert_called()
    mock.on_begin_wrap.assert_called()
    mock.on_finish_wrap.assert_called()

    assert queries == expected


def test_complex_composition_map(composition_listener):
    listener, mock, queries = composition_listener

    class CompositedItem(Composition):
        _listener = listener
        pass

    @dataclasses.dataclass(frozen=True)
    class Item(CompositableItem[str, CompositedItem]):
        name: str

    item1 = Item("hello")
    item2 = Item("world")
    item3 = Item("lorem")
    item4 = Item("ipsum")
    composited = item1 | item2 & (item3 | item4)
    assert composited.left == item1
    assert isinstance(composited.right, CompositedItem)
    assert composited.right.left == item2
    assert isinstance(composited.right.right, CompositedItem)
    assert composited.right.right.left == item3
    assert composited.right.right.right == item4

    # fmt: off
    expected = [
        "(",
            item1,
            EnumOperand.OR,
            "(",
                item2,
                EnumOperand.AND,
                "(",
                    item3,
                    EnumOperand.OR,
                    item4,
                ")",
            ")",
        ")",
    ]
    # fmt: on

    composited.map()

    mock.on_composite.assert_called()
    mock.on_begin_wrap.assert_called()
    mock.on_finish_wrap.assert_called()

    assert queries == expected
