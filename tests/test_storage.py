"""D1 result shapes the Python Workers runtime can return, faked without Pyodide."""

import asyncio

import pytest

from storage import D1Database


class JsProxy:
    """Mimics a Pyodide proxy: to_py() returns the wrapped value."""

    def __init__(self, value):
        self.value = value

    def to_py(self):
        return self.value


class JsObject:
    """A plain JS object that to_py() left as a proxy; exposes object_entries()."""

    def __init__(self, data):
        self.data = data

    def object_entries(self):
        return list(self.data.items())


class Binding:
    def __init__(self, result):
        self.result = result
        self.bound = None

    def prepare(self, sql):
        return self

    def bind(self, *params):
        self.bound = params
        return self

    async def all(self):
        return self.result


ROW = {"id": "a", "n": 1}


@pytest.mark.parametrize("result", [
    JsProxy({"results": [ROW], "success": True}),           # whole result converts to a dict
    {"results": [ROW]},                                    # SDK already returns Python
    type("R", (), {"results": JsProxy([ROW])})(),          # attribute access, rows proxy
    type("R", (), {"results": JsProxy([JsObject(ROW)])})(),  # rows stay JS objects
])
def test_d1_result_shapes(result):
    assert asyncio.run(D1Database(Binding(result)).all("SELECT 1")) == [ROW]


def test_empty_result():
    assert asyncio.run(D1Database(Binding({"results": None})).all("SELECT 1")) == []


def test_params_are_bound():
    b = Binding({"results": []})
    asyncio.run(D1Database(b).all("SELECT ?", ["x", 3]))
    assert b.bound == ("x", 3)
