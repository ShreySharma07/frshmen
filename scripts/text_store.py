"""The pipeline's side of the job-text store: writes descriptions to Cloudflare R2 over its
S3-compatible API (docs/decisions.md, 2026-11-11 storage; setup in docs/setup-r2.md).

Free tier (checked 2026-11-11): 10 GB stored, 1M writes and 10M reads a month, no egress fee.
Only new or changed jobs are written, so a normal run is a few hundred writes.

Needs R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET. With none of them set
the store is simply off, so the pipeline runs as before until R2 is set up.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api" / "src"))  # the key is shared with the API
from job_text import key  # noqa: E402

ENV = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
WORKERS = 16  # uploads in parallel; R2 has no per-bucket rate limit at this size


class TextStore:
    """`client` is a boto3 S3 client (or anything with put_object / get_object / delete_objects)."""

    def __init__(self, client: Any, bucket: str):
        self.client, self.bucket = client, bucket

    def put(self, job_id: str, text: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key(job_id), Body=text.encode(),
                               ContentType="text/plain; charset=utf-8")

    def put_many(self, items: Iterable[tuple[str, str]]) -> int:
        """Upload (job id, text) pairs. Raises on the first failure, so the caller can roll back
        and the next run writes them again (a PUT of the same text is harmless)."""
        todo = [(jid, text) for jid, text in items if text]
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(lambda it: self.put(*it), todo))
        return len(todo)

    def get(self, job_id: str) -> str | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key(job_id))["Body"].read().decode()
        except self.client.exceptions.NoSuchKey:
            return None

    def delete_many(self, job_ids: Iterable[str]) -> int:
        ids = list(job_ids)
        for i in range(0, len(ids), 1000):  # the API takes at most 1,000 keys a call
            self.client.delete_objects(Bucket=self.bucket,
                                       Delete={"Objects": [{"Key": key(j)} for j in ids[i:i + 1000]], "Quiet": True})
        return len(ids)


def from_env(env: dict[str, str] | None = None) -> TextStore | None:
    """The store described by the R2_* variables; None when none are set. Some but not all set is
    a mistake worth stopping for, rather than silently not storing text."""
    env = os.environ if env is None else env
    have = [name for name in ENV if env.get(name)]
    if not have:
        return None
    if len(have) != len(ENV):
        sys.exit("R2 is half configured: missing " + ", ".join(n for n in ENV if n not in have))
    import boto3  # imported here so the rest of the pipeline runs without it
    from botocore.config import Config

    client = boto3.client(
        "s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com", region_name="auto",
        aws_access_key_id=env["R2_ACCESS_KEY_ID"], aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        # Newer boto3 adds checksum headers by default; ask for them only where the API requires
        # them, which is what R2 documents.
        config=Config(request_checksum_calculation="when_required", response_checksum_validation="when_required",
                      retries={"max_attempts": 4, "mode": "standard"}))
    return TextStore(client, env["R2_BUCKET"])
