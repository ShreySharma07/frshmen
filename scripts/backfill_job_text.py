"""Copy every stored job description from the jobs table to Supabase Storage, once
(docs/decisions.md, 2026-11-12). New and changed jobs are written by publish_pg.py; this covers
the jobs that were already stored. Safe to run twice: writing the same text again changes nothing.

The jobs table keeps its copy. Dropping that column is a later, separate step, taken only after
--verify passes.

Run:
  SUPABASE_DB_URL=... SUPABASE_URL=... SUPABASE_SECRET_KEY=... \\
    python scripts/backfill_job_text.py [--dry-run] [--verify 200]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from text_store import TextStore, from_env  # noqa: E402

BATCH = 500
WITH_TEXT = "description_text IS NOT NULL AND description_text <> ''"


def copy_all(pg: psycopg.Connection, store: TextStore | None, log=print) -> tuple[int, int]:
    """Upload every job's text, in id order. Returns (jobs, bytes). With no store, only counts."""
    jobs = size = 0
    last = ""
    while True:
        # Keyset paging: each batch is its own short query, so nothing is held open on the
        # pooled connection while uploads run.
        rows = pg.execute(f"SELECT id, description_text FROM jobs WHERE {WITH_TEXT} AND id > %s ORDER BY id LIMIT %s",
                          (last, BATCH)).fetchall()
        if not rows:
            return jobs, size
        if store is not None:
            store.put_many(rows)
        jobs += len(rows)
        size += sum(len(text.encode()) for _, text in rows)
        last = rows[-1][0]
        log(f"  {jobs:,} jobs, {size / 1024 / 1024:.1f} MB")


def verify(pg: psycopg.Connection, store: TextStore, sample: int) -> list[str]:
    """Ids from a random sample whose stored text is missing or differs from the column."""
    rows = pg.execute(f"SELECT id, description_text FROM jobs WHERE {WITH_TEXT} ORDER BY random() LIMIT %s",
                      (sample,)).fetchall()
    return [jid for jid, text in rows if store.get(jid) != text]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="count jobs and bytes, upload nothing")
    parser.add_argument("--verify", type=int, default=0, metavar="N", help="afterwards compare N random jobs with Storage")
    args = parser.parse_args()
    url = os.environ.get("SUPABASE_DB_URL") or sys.exit("set SUPABASE_DB_URL")
    store = None if args.dry_run else (from_env() or sys.exit("set SUPABASE_URL and SUPABASE_SECRET_KEY (docs/setup-job-text.md)"))
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as pg:
        jobs, size = copy_all(pg, store)
        print(f"{'would copy' if args.dry_run else 'copied'} {jobs:,} descriptions, {size / 1024 / 1024:.1f} MB")
        if store is not None and args.verify:
            bad = verify(pg, store, args.verify)
            if bad:
                print(f"verify FAILED for {len(bad)} of {args.verify}: {bad[:10]}")
                return 1
            print(f"verify passed: {args.verify} random jobs match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
