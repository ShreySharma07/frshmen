"""Database adapters with one async interface: `await db.all(sql, params) -> list[dict]`.

D1 in the Worker, SQLite for local dev and tests, so the API code is the same in both.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Protocol, Sequence


class Database(Protocol):
    async def all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]: ...


class D1Database:
    """Wraps the Worker's D1 binding (env.DB)."""

    def __init__(self, binding: Any):
        self.binding = binding

    async def all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        stmt = self.binding.prepare(sql)
        if params:
            # Never bind None: Pyodide passes it as `undefined`, which D1 rejects.
            stmt = stmt.bind(*params)
        result = await stmt.all()
        return [_to_dict(row) for row in _rows(result)]


def _py(value: Any) -> Any:
    """Convert a Pyodide JsProxy to Python; leave Python values alone."""
    return value.to_py() if hasattr(value, "to_py") else value


def _rows(result: Any) -> list[Any]:
    # Depending on the Workers SDK version, D1's result is a JsProxy or already a dict.
    result = _py(result)
    rows = result.get("results") if isinstance(result, dict) else getattr(result, "results", None)
    return list(_py(rows) or [])


def _to_dict(row: Any) -> dict[str, Any]:
    row = _py(row)
    if isinstance(row, dict):
        return row
    if hasattr(row, "object_entries"):  # plain JS object that to_py() left as a proxy
        return {k: _py(v) for k, v in row.object_entries()}
    return dict(row)


class SqliteDatabase:
    def __init__(self, path: str):
        self.path = path

    async def all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        finally:
            conn.close()
