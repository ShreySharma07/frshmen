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
        return [dict(row) for row in result.results.to_py()]


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
