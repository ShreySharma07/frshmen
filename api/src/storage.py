"""Database access with one async interface: `await db.all(sql, params) -> list[dict]`.

Supabase Postgres through asyncpg (docs/decisions.md, 2026-10-15/16). In the Worker the
connection goes through the Hyperdrive binding, which keeps a pool open to Supabase, so
opening one connection per request is cheap; locally and in tests it's a plain DSN.
SQL uses $1, $2 ... placeholders.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Protocol, Sequence

import asyncpg


class Database(Protocol):
    async def all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]: ...


class PostgresDatabase:
    def __init__(self, conn: Any):
        self.conn = conn

    async def all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in await self.conn.fetch(sql, *params)]


@asynccontextmanager
async def connect(*, dsn: str | None = None, hyperdrive: Any = None) -> AsyncIterator[PostgresDatabase]:
    if hyperdrive is not None:
        # Hyperdrive terminates TLS to Supabase itself; the Worker -> Hyperdrive hop is local.
        conn = await asyncpg.connect(host=hyperdrive.host, port=int(hyperdrive.port), user=hyperdrive.user,
                                     password=hyperdrive.password, database=hyperdrive.database, ssl=False,
                                     # Hyperdrive pools per transaction, so don't keep named statements.
                                     statement_cache_size=0)
    else:
        conn = await asyncpg.connect(dsn)
    try:
        yield PostgresDatabase(conn)
    finally:
        await conn.close()
