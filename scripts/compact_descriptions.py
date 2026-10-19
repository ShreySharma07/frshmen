"""One-off: shrink stored descriptions to the sections a candidate needs (extract/stored_text.py).

New and changed jobs are stored compact by fetch_jobs.py. Jobs whose text hasn't changed since are
never rewritten by the pipeline (same content_hash), so this rewrites them once, using each job's
stored label evidence so the YoE line behind its label stays visible. Running it again changes
nothing: compacting a compact text gives the same text.

  SUPABASE_DB_URL=postgresql://... python scripts/compact_descriptions.py [--dry-run] [--vacuum-full]

Supabase's 500 MB counts the whole database, including the old row versions an UPDATE leaves
behind, so --vacuum-full rewrites the jobs table afterwards to hand the space back. It locks the
table while it runs (seconds at our size); run it between pipeline runs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extract.stored_text import compact  # noqa: E402

BATCH = 500

SELECT = """
SELECT j.id, j.description_text, l.evidence -> 'level'
FROM jobs j LEFT JOIN current_labels l ON l.job_id = j.id
WHERE j.description_text IS NOT NULL AND j.id > %s
ORDER BY j.id LIMIT %s
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report the saving, write nothing")
    parser.add_argument("--vacuum-full", action="store_true", help="rewrite the jobs table afterwards to free the space")
    args = parser.parse_args()
    url = os.environ.get("SUPABASE_DB_URL") or sys.exit("set SUPABASE_DB_URL")

    before = after = changed = seen = 0
    last = ""
    with psycopg.connect(url, prepare_threshold=None) as pg:
        print(f"Database size: {_size(pg)}")
        while True:
            rows = pg.execute(SELECT, (last, BATCH)).fetchall()
            if not rows:
                break
            updates = []
            for job_id, text, evidence in rows:
                short = compact(text, evidence if isinstance(evidence, list) else [])
                before, after, seen = before + len(text), after + len(short), seen + 1
                if short != text:
                    updates.append((short, job_id))
            if updates and not args.dry_run:
                with pg.cursor() as cur:
                    cur.executemany("UPDATE jobs SET description_text = %s WHERE id = %s", updates)
                pg.commit()
            changed += len(updates)
            last = rows[-1][0]
            print(f"{seen} jobs read, {changed} {'to shrink' if args.dry_run else 'shrunk'}", flush=True)

        if args.vacuum_full and not args.dry_run:
            pg.commit()
            pg.autocommit = True  # VACUUM can't run inside a transaction
            pg.execute("VACUUM (FULL, ANALYZE) jobs")
        print(f"Database size: {_size(pg)}")

    pct = round(100 * after / before) if before else 100
    print(f"\nDescriptions: {before / 1e6:.1f}M -> {after / 1e6:.1f}M characters ({pct}% kept), "
          f"{changed} of {seen} jobs {'would change' if args.dry_run else 'changed'}.")
    return 0


def _size(pg: psycopg.Connection) -> str:
    return pg.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]


if __name__ == "__main__":
    sys.exit(main())
