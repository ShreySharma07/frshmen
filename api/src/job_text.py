"""Job descriptions kept outside Postgres, in a Cloudflare R2 bucket (docs/decisions.md,
2026-11-11 storage). Postgres holds what lists and filters need; the long text is read from R2
only when one job is opened. During the switch-over both hold the text, and a miss here falls
back to the database column.

Shared by the pipeline (scripts/text_store.py writes with the same key) and the API Worker,
which reads through its R2 binding.
"""

from __future__ import annotations

import hashlib
from typing import Any

BINDING = "JOB_TEXT"  # the R2 binding's name in api/wrangler.jsonc


def key(job_id: str) -> str:
    """Where a job's text lives. Hashed because job ids contain ':' and '/', and so that keys
    spread evenly and never exceed R2's key length."""
    return "text/" + hashlib.sha256(job_id.encode()).hexdigest()


def bucket_of(request: Any) -> Any:
    """The R2 bucket for this request: the Worker's binding, or a stand-in set on app.state in tests."""
    env = request.scope.get("env")
    return getattr(env, BINDING, None) or getattr(request.app.state, "job_text", None)


async def read(bucket: Any, job_id: str) -> str | None:
    """The stored text, or None when there is no bucket, no object, or R2 failed. A failure is
    printed (Workers Logs) and never breaks the page: the caller falls back to the database."""
    if bucket is None:
        return None
    try:
        obj = await bucket.get(key(job_id))
        return None if obj is None else str(await obj.text())
    except Exception as exc:  # noqa: BLE001 - the R2 binding raises JS errors of no fixed type
        print(f"job_text: reading {job_id} from R2 failed: {exc!r}")
        return None
