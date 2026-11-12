"""Job descriptions kept outside the jobs table, in Supabase Storage (docs/decisions.md,
2026-11-12). Postgres holds what lists and filters need; the long text is read from the public
`job-text` bucket only when one job is opened. During the switch-over both hold the text, and a
miss here falls back to the database column.

Shared by the pipeline (scripts/text_store.py writes with the same key) and the API Worker.
The Worker reads only when its JOB_TEXT var is "on" (set at deploy from the repo variable of
that name), so before the bucket is filled no request pays for a lookup that would miss.
"""

from __future__ import annotations

import hashlib
from typing import Any, Awaitable, Callable

BUCKET = "job-text"
# job id -> the stored text, or None when it isn't there.
Read = Callable[[str], Awaitable[str | None]]


def key(job_id: str) -> str:
    """Where a job's text lives. Hashed because job ids contain ':' and '/', and so that object
    names stay short and safe in a URL."""
    return hashlib.sha256(job_id.encode()).hexdigest() + ".txt"


def public_url(base: str, job_id: str) -> str:
    return f"{base.rstrip('/')}/storage/v1/object/public/{BUCKET}/{key(job_id)}"


def reader(request: Any) -> Read | None:
    """How this request reads job text: a stand-in set on app.state in tests, the bucket's public
    URL in the Worker, or None when the store is off."""
    override = getattr(request.app.state, "job_text", None)
    if override is not None:
        return override
    env = request.scope.get("env")
    base = str(getattr(env, "SUPABASE_URL", "") or "") if env is not None else ""
    if not base or str(getattr(env, "JOB_TEXT", "") or "") != "on":
        return None

    async def read(job_id: str) -> str | None:
        return await worker_get_text(public_url(base, job_id))
    return read


async def read(source: Read | None, job_id: str) -> str | None:
    """The stored text, or None when the store is off, has no such job, or failed. A failure is
    printed (Workers Logs) and never breaks the page: the caller falls back to the database."""
    if source is None:
        return None
    try:
        return await source(job_id)
    except Exception as exc:  # noqa: BLE001 - whatever the fetch raises, the page must still load
        print(f"job_text: reading {job_id} failed: {exc!r}")
        return None


async def worker_get_text(url: str) -> str | None:
    """The Worker's outbound request. pyodide.http exists only inside the Workers runtime."""
    from pyodide.http import pyfetch  # type: ignore[import-not-found]

    resp = await pyfetch(url, method="GET")
    if resp.status == 200:
        return await resp.string()
    if resp.status in (400, 404):  # Storage answers 400 for an object that isn't there
        return None
    raise RuntimeError(f"storage answered {resp.status}")
