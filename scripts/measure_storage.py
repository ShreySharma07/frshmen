"""Measure what a stored job costs, so the worldwide plan rests on numbers instead of estimates
(docs/strategy/worldwide-coverage.md, phase 0). Read-only.

Reports the database's size against Supabase's free 500 MB, each table with its indexes, how
much of the jobs table is description text, the cost of one job without that text, how many
jobs fit once the text lives in Supabase Storage, and open jobs per careers system.

Run:
  SUPABASE_DB_URL=postgresql://... python scripts/measure_storage.py [--alert]

With --alert (the daily run, .github/workflows/measure-storage.yml) it fails when the database passes
ALERT_SHARE of the free tier, so GitHub emails the repo owner (security review M3, 2026-11-18):
throwaway accounts or a runaway table get noticed before Supabase stops taking writes.
"""

from __future__ import annotations

import os
import sys

import psycopg

FREE_BYTES = 500 * 1024 * 1024  # Supabase free tier
HEADROOM = 0.85  # plan to fill at most this share: indexes bloat and migrations need room
ALERT_SHARE = 0.80  # the daily check fails past this
# The most any one person stores (chats, LinkedIn connections, resume structure): sizes only, never who.
PER_PERSON = """
SELECT s.id,
       COALESCE((SELECT sum(pg_column_size(c.*)) FROM agent_chats c WHERE c.student_id = s.id), 0)
     + COALESCE((SELECT sum(pg_column_size(n.*)) FROM connections n WHERE n.student_id = s.id), 0)
     + COALESCE(pg_column_size(s.resume_doc), 0) + COALESCE(pg_column_size(s.resume_text), 0) AS bytes
FROM students s ORDER BY bytes DESC LIMIT 5
"""

TABLES = """
SELECT relname, n_live_tup AS rows, pg_table_size(relid) AS table_bytes,
       pg_indexes_size(relid) AS index_bytes, pg_total_relation_size(relid) AS total_bytes
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY total_bytes DESC
"""
# pg_column_size is the stored size (after Postgres compresses long text), which is what counts.
JOBS = """
SELECT count(*) AS jobs,
       count(*) FILTER (WHERE status = 'open') AS open,
       count(*) FILTER (WHERE description_text IS NOT NULL AND description_text <> '') AS with_text,
       COALESCE(sum(pg_column_size(description_text)), 0) AS text_stored,
       COALESCE(sum(octet_length(description_text)), 0) AS text_raw,
       COALESCE(sum(pg_column_size(j.*)), 0) AS rows_stored
FROM jobs j
"""
BY_SOURCE = """
SELECT source, count(*) FILTER (WHERE status = 'open') AS open, count(*) AS total,
       COALESCE(avg(octet_length(description_text)) FILTER (WHERE status = 'open'), 0)::int AS avg_text
FROM jobs GROUP BY source ORDER BY open DESC
"""


def mb(n: float) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def report(pg: psycopg.Connection) -> str:
    db_bytes = pg.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    tables = pg.execute(TABLES).fetchall()
    jobs, open_jobs, with_text, text_stored, text_raw, rows_stored = pg.execute(JOBS).fetchone()
    sources = pg.execute(BY_SOURCE).fetchall()
    people = [int(r[1]) for r in pg.execute(PER_PERSON).fetchall()]
    students = pg.execute("SELECT count(*) FROM students").fetchone()[0]
    ours = sum(t[4] for t in tables)  # the rest of the database is Supabase's own schemas

    out = ["## Storage", "",
           f"- Database: **{mb(db_bytes)}** of {mb(FREE_BYTES)} ({db_bytes / FREE_BYTES:.0%}); "
           f"our tables and indexes are {mb(ours)} of that.",
           f"- People: {students:,}; the five who store the most use "
           f"{', '.join(mb(b) for b in people) or 'nothing'} (chats, connections and resume).",
           f"- Jobs stored: **{jobs:,}** ({open_jobs:,} open, {jobs - open_jobs:,} closed), {with_text:,} with text.",
           "", "| Table | Rows | Table | Indexes | Total |", "|---|---:|---:|---:|---:|"]
    out += [f"| {name} | {rows:,} | {mb(t)} | {mb(i)} | {mb(total)} |" for name, rows, t, i, total in tables[:12]]

    if jobs:
        # Everything in our tables except the description text, spread over the jobs: labels,
        # indexes and the job row itself. This is what a job costs once its text is in Storage.
        slim = (ours - text_stored) / jobs
        fits = int(FREE_BYTES * HEADROOM / slim) if slim > 0 else 0
        out += ["", "## What one job costs", "",
                f"- Description text: {mb(text_stored)} stored ({mb(text_raw)} before Postgres compresses it), "
                f"**{text_stored / max(with_text, 1):,.0f} bytes** a job on average.",
                f"- Everything else (row, labels, indexes): **{slim:,.0f} bytes** a job.",
                f"- With the text in Storage and {HEADROOM:.0%} of the free tier used, Postgres holds about "
                f"**{fits:,} jobs** (open and closed together).",
                f"- In Storage the same text is {text_raw / max(with_text, 1):,.0f} bytes a job uncompressed, so the "
                f"free 1 GB holds about {int(1024**3 / max(text_raw / max(with_text, 1), 1)):,} jobs."]
    out += ["", "## Open jobs by careers system", "", "| System | Open | All | Avg text, bytes |", "|---|---:|---:|---:|"]
    out += [f"| {src} | {o:,} | {total:,} | {avg:,} |" for src, o, total, avg in sources]
    return "\n".join(out) + "\n"


def over_limit(pg: psycopg.Connection) -> str | None:
    """Why the daily check should fail, or None."""
    db_bytes = pg.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    if db_bytes > ALERT_SHARE * FREE_BYTES:
        return (f"The database is {mb(db_bytes)}, past {ALERT_SHARE:.0%} of the free {mb(FREE_BYTES)}. "
                "Look at the biggest tables and people above before Supabase stops taking writes.")
    return None


def main() -> int:
    url = os.environ.get("SUPABASE_DB_URL") or sys.exit("set SUPABASE_DB_URL")
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as pg:
        text = report(pg)
        alarm = over_limit(pg) if "--alert" in sys.argv else None
    if alarm:
        text += f"\n\n## Alert\n\n{alarm}\n"
    print(text)
    # In GitHub Actions the same report shows on the run's summary page.
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as f:
            f.write(text)
    if alarm:
        print(f"::error::{alarm}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
