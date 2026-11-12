"""The pipeline's side of the job-text store: writes descriptions to the `job-text` bucket in
Supabase Storage over its REST API (docs/decisions.md, 2026-11-12; setup in
docs/setup-job-text.md).

Free tier (checked 2026-11-12): 1 GB of files, no card. At about 2.3 KB a description that is
roughly 400,000 jobs. Only new or changed jobs are written, a few hundred a run.

Needs SUPABASE_URL and SUPABASE_SECRET_KEY (the project's secret or service-role key, which may
write to any bucket; it lives only in GitHub Actions secrets). With neither set the store is
off, so the pipeline runs as before until it is set up.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api" / "src"))  # the key is shared with the API
from job_text import BUCKET, key  # noqa: E402

ENV = ("SUPABASE_URL", "SUPABASE_SECRET_KEY")
WORKERS = 8  # uploads in parallel, all to our own project
TIMEOUT = 30
# (method, url, headers, body) -> (status, body). Tests pass a fake; `send` below is the real one.
Send = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]


def send(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 - always our Supabase URL
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class TextStore:
    def __init__(self, base_url: str, secret: str, send: Send = send):
        self.objects = f"{base_url.rstrip('/')}/storage/v1/object/{BUCKET}"
        self.auth = {"apikey": secret, "Authorization": f"Bearer {secret}"}
        self.send = send

    def put(self, job_id: str, text: str) -> None:
        # x-upsert: writing a job again replaces its text instead of failing as a duplicate.
        status, body = self.send("POST", f"{self.objects}/{key(job_id)}",
                                 {**self.auth, "Content-Type": "text/plain; charset=utf-8", "x-upsert": "true"},
                                 text.encode())
        if status != 200:
            raise RuntimeError(f"storing text for {job_id} failed: {status} {body[:200]!r}")

    def put_many(self, items: Iterable[tuple[str, str]]) -> int:
        """Upload (job id, text) pairs. Raises on the first failure, so the caller can roll back
        and the next run writes them again (writing the same text twice is harmless)."""
        todo = [(jid, text) for jid, text in items if text]
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(lambda it: self.put(*it), todo))
        return len(todo)

    def get(self, job_id: str) -> str | None:
        status, body = self.send("GET", f"{self.objects}/{key(job_id)}", self.auth, None)
        if status == 200:
            return body.decode()
        if status in (400, 404):  # Storage answers 400 for an object that isn't there
            return None
        raise RuntimeError(f"reading text for {job_id} failed: {status} {body[:200]!r}")

    def delete_many(self, job_ids: Iterable[str]) -> int:
        ids = list(job_ids)
        for i in range(0, len(ids), 500):
            status, body = self.send("DELETE", self.objects, {**self.auth, "Content-Type": "application/json"},
                                     json.dumps({"prefixes": [key(j) for j in ids[i:i + 500]]}).encode())
            if status != 200:
                raise RuntimeError(f"deleting text failed: {status} {body[:200]!r}")
        return len(ids)


def from_env(env: dict[str, str] | None = None) -> TextStore | None:
    """The store described by the environment; None when neither variable is set. One without
    the other is a mistake worth stopping for, rather than silently not storing text."""
    env = os.environ if env is None else env
    have = [name for name in ENV if env.get(name)]
    if not have:
        return None
    if len(have) != len(ENV):
        sys.exit("the job-text store is half configured: missing " + ", ".join(n for n in ENV if n not in have))
    return TextStore(env["SUPABASE_URL"], env["SUPABASE_SECRET_KEY"])
