"""Jobs an admin added by hand in /admin (db/postgres/0012_manual_jobs.sql).

Not an ATS adapter (nothing is fetched over HTTP), so it isn't in ADAPTERS: fetch_jobs.py reads
it straight from the database when SUPABASE_DB_URL is set.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from sources.models import Job

NAME = "manual"


def slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def to_job(row: dict[str, Any]) -> Job:
    company = row["company"].strip()
    return Job(source=NAME, external_id=str(row["id"]), company=company, company_slug=slug(company),
               title=row["title"].strip(), url=row["url"], location_raw=(row.get("location_raw") or "").strip(),
               description_text=row["description_text"], posted_at=_iso(row.get("posted_at")))


def load(dsn: str) -> tuple[list[Job], list[dict[str, str]]]:
    """(open jobs, boards). Every company that ever had a manual job counts as a board that
    answered, so publish_pg.py closes a job once its row is closed."""
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        rows = conn.execute("SELECT id, company, title, url, location_raw, description_text, posted_at, closed_at "
                            "FROM manual_jobs ORDER BY id").fetchall()
    jobs = [to_job(r) for r in rows if r["closed_at"] is None]
    boards = [{"source": NAME, "company_slug": s} for s in sorted({slug(r["company"]) for r in rows})]
    return jobs, boards
