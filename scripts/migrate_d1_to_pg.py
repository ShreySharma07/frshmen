"""Copy every job from D1 into Supabase Postgres (M3, docs/plan.md §13).

Order: companies -> jobs -> job_labels (each table only points at tables already filled),
then the pipeline's runs and meta rows. Safe to run again at any time:
- every write is an upsert on a stable key (company name, job id, job id + rules version),
  so a second run gives the same result as the first
- jobs go in batches of BATCH, one transaction each: a dropped connection loses one batch,
  and re-running carries on from there
- unchanged rows aren't rewritten (content_hash / label_hash compare)
- at the end, row counts per status, level and company are compared with D1; any
  difference fails the run

Run:
  python scripts/migrate_d1_to_pg.py --dry-run                  # read D1, check, write nothing
  SUPABASE_DB_URL=postgresql://... python scripts/migrate_d1_to_pg.py
  python scripts/migrate_d1_to_pg.py --sqlite data/local.db     # local SQLite instead of D1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from publish_d1 import Database, SqliteDatabase, WranglerD1  # noqa: E402

BATCH = 500
LOCATION_TYPES = {"remote", "hybrid", "onsite"}
VISA = {"yes", "no", "unknown"}
LABEL_FIELDS = [
    "level", "level_confidence", "level_reason", "yoe_min", "yoe_max", "yoe_evidence", "batch_years",
    "role_match", "role_family", "location_type", "countries", "cities", "eligible",
    "visa_sponsorship", "skills", "evidence",
]


# --- Reading D1 ------------------------------------------------------------------------------

def d1_pages(db: Database, table: str = "jobs") -> Iterator[list[dict[str, Any]]]:
    """Every row, BATCH at a time, by primary key: each page is an index range read."""
    last = ""
    while True:
        rows = db.query(f"SELECT * FROM {table} WHERE id > '{last.replace(chr(39), chr(39) * 2)}' "
                        f"ORDER BY id LIMIT {BATCH}")
        if not rows:
            return
        yield rows
        last = rows[-1]["id"]


def d1_counts(db: Database) -> dict[str, Counter]:
    return {
        "status": Counter({r["k"]: r["n"] for r in db.query("SELECT status AS k, COUNT(*) AS n FROM jobs GROUP BY 1")}),
        "level": Counter({r["k"]: r["n"] for r in db.query("SELECT level AS k, COUNT(*) AS n FROM jobs GROUP BY 1")}),
        "company": Counter({r["k"]: r["n"] for r in db.query("SELECT company AS k, COUNT(*) AS n FROM jobs GROUP BY 1")}),
    }


def _table_exists(db: Database, name: str) -> bool:
    return bool(db.query(f"SELECT name FROM sqlite_master WHERE type = 'table' AND name = '{name}'"))


# --- Turning D1 rows into Postgres rows ------------------------------------------------------

def _json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _ts(value: Any) -> datetime | None:
    """D1 stores ISO text; anything unparseable becomes NULL rather than failing the batch."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _texts(value: Any) -> list[str]:
    items = _json(value, [])
    return [str(x) for x in items] if isinstance(items, list) else []


def job_row(r: dict[str, Any], company_id: int) -> dict[str, Any]:
    return {
        "id": r["id"],
        "company_id": company_id,
        "source": r["source"],
        "title": r["title"],
        "url": r["url"],
        "location_raw": r.get("location_raw"),
        "department": r.get("department"),
        "employment_type": r.get("employment_type"),
        "posted_at": _ts(r.get("posted_at")),
        "first_seen_at": _ts(r.get("first_seen_at")) or datetime.now(timezone.utc),
        "status": r.get("status") if r.get("status") in ("open", "closed") else "open",
        "missed_runs": int(r.get("missed_runs") or 0),
        "description_text": r.get("description_text"),
        "content_hash": r["content_hash"],
    }


def label_row(r: dict[str, Any]) -> dict[str, Any]:
    batch = [int(y) for y in _json(r.get("batch_years"), []) if str(y).isdigit()]
    row = {
        "job_id": r["id"],
        "rules_version": int(r.get("extract_version") or 0),
        "level": r["level"],
        "level_confidence": r.get("level_confidence"),
        "level_reason": r.get("level_reason"),
        "yoe_min": r.get("yoe_min"),
        "yoe_max": r.get("yoe_max"),
        "yoe_evidence": r.get("yoe_evidence"),
        "batch_years": batch,
        "role_match": bool(r.get("role_match")),
        "role_family": r.get("role_family"),
        "location_type": r.get("location_type") if r.get("location_type") in LOCATION_TYPES else None,
        "countries": _texts(r.get("countries")),
        "cities": _texts(r.get("cities")),
        "eligible": bool(r.get("eligible", 1)),
        "visa_sponsorship": r.get("visa_sponsorship") if r.get("visa_sponsorship") in VISA else "unknown",
        "skills": _texts(r.get("skills")),
        "evidence": _json(r.get("evidence"), None),
    }
    # D1's extract_hash covers the same values; older rows lack it, so hash what we store.
    row["label_hash"] = r.get("extract_hash") or hashlib.sha256(
        json.dumps({k: row[k] for k in LABEL_FIELDS}, sort_keys=True, default=str).encode()).hexdigest()
    row["evidence"] = Jsonb(row["evidence"]) if row["evidence"] is not None else None
    return row


# --- Writing Postgres ------------------------------------------------------------------------

UPSERT_COMPANY = "INSERT INTO companies (name) VALUES (%s) ON CONFLICT (name) DO NOTHING"

UPSERT_JOB = """
INSERT INTO jobs (id, company_id, source, title, url, location_raw, department, employment_type,
                  posted_at, first_seen_at, status, missed_runs, description_text, content_hash)
VALUES (%(id)s, %(company_id)s, %(source)s, %(title)s, %(url)s, %(location_raw)s, %(department)s,
        %(employment_type)s, %(posted_at)s, %(first_seen_at)s, %(status)s, %(missed_runs)s,
        %(description_text)s, %(content_hash)s)
ON CONFLICT (id) DO UPDATE SET
  company_id = EXCLUDED.company_id, source = EXCLUDED.source, title = EXCLUDED.title,
  url = EXCLUDED.url, location_raw = EXCLUDED.location_raw, department = EXCLUDED.department,
  employment_type = EXCLUDED.employment_type, posted_at = EXCLUDED.posted_at,
  first_seen_at = EXCLUDED.first_seen_at, status = EXCLUDED.status,
  missed_runs = EXCLUDED.missed_runs, description_text = EXCLUDED.description_text,
  content_hash = EXCLUDED.content_hash
WHERE (jobs.content_hash, jobs.status, jobs.missed_runs, jobs.posted_at)
      IS DISTINCT FROM (EXCLUDED.content_hash, EXCLUDED.status, EXCLUDED.missed_runs, EXCLUDED.posted_at)
"""

_LCOLS = ["job_id", "rules_version", "label_hash", *LABEL_FIELDS]
UPSERT_LABEL = f"""
INSERT INTO job_labels ({", ".join(_LCOLS)})
VALUES ({", ".join(f"%({c})s" for c in _LCOLS)})
ON CONFLICT (job_id, rules_version) DO UPDATE SET
  {", ".join(f"{c} = EXCLUDED.{c}" for c in ["label_hash", *LABEL_FIELDS])}, labelled_at = now()
WHERE job_labels.label_hash <> EXCLUDED.label_hash
"""


def copy_jobs(db: Database, pg: psycopg.Connection | None) -> tuple[int, int]:
    """Returns (jobs read, batches written). pg=None is a dry run: transform and check only."""
    company_ids: dict[str, int] = {}
    read = batches = 0
    for rows in d1_pages(db):
        read += len(rows)
        if pg is None:
            for r in rows:
                job_row(r, 0), label_row(r)  # raises on anything the real run would choke on
            continue
        with pg.transaction(), pg.cursor() as cur:
            new = sorted({r["company"] for r in rows} - company_ids.keys())
            if new:
                cur.executemany(UPSERT_COMPANY, [(n,) for n in new])
                cur.execute("SELECT name, id FROM companies WHERE name = ANY(%s)", (new,))
                company_ids.update(dict(cur.fetchall()))
            cur.executemany(UPSERT_JOB, [job_row(r, company_ids[r["company"]]) for r in rows])
            cur.executemany(UPSERT_LABEL, [label_row(r) for r in rows])
        batches += 1
        print(f"  batch {batches}: {read} jobs", flush=True)
    return read, batches


def copy_bookkeeping(db: Database, pg: psycopg.Connection) -> None:
    runs = db.query("SELECT * FROM runs ORDER BY id")
    meta = db.query("SELECT * FROM meta") if _table_exists(db, "meta") else []
    with pg.transaction(), pg.cursor() as cur:
        cur.executemany(
            "INSERT INTO runs (id, finished_at, companies_ok, companies_failed, jobs_seen, jobs_new, "
            "jobs_changed, jobs_closed, errors) OVERRIDING SYSTEM VALUE "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            [(r["id"], _ts(r["finished_at"]), r["companies_ok"], r["companies_failed"], r["jobs_seen"],
              r["jobs_new"], r["jobs_changed"], r["jobs_closed"], Jsonb(_json(r.get("errors"), {})))
             for r in runs])
        # Copied ids are explicit, so move the identity past them for the pipeline's next insert.
        cur.execute("SELECT setval(pg_get_serial_sequence('runs', 'id'), GREATEST((SELECT MAX(id) FROM runs), 1))")
        cur.executemany(
            "INSERT INTO meta (key, value, updated_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
            [(m["key"], Jsonb(_json(m["value"], None)), _ts(m["updated_at"])) for m in meta])
    print(f"  runs: {len(runs)}, meta: {len(meta)}")


def pg_counts(pg: psycopg.Connection) -> dict[str, Counter]:
    with pg.cursor() as cur:
        cur.execute("SELECT status, COUNT(*) FROM jobs GROUP BY 1")
        status = Counter(dict(cur.fetchall()))
        cur.execute("SELECT level, COUNT(*) FROM current_labels GROUP BY 1")
        level = Counter(dict(cur.fetchall()))
        cur.execute("SELECT c.name, COUNT(*) FROM jobs j JOIN companies c ON c.id = j.company_id GROUP BY 1")
        company = Counter(dict(cur.fetchall()))
    return {"status": status, "level": level, "company": company}


def differences(source: dict[str, Counter], target: dict[str, Counter]) -> list[str]:
    out = []
    for kind in source:
        for key in sorted(set(source[kind]) | set(target[kind]), key=str):
            if source[kind][key] != target[kind][key]:
                out.append(f"{kind} {key!r}: D1 {source[kind][key]}, Postgres {target[kind][key]}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--d1", default="frshmen", help="D1 database name")
    parser.add_argument("--config", type=Path, default=ROOT / "api" / "wrangler.jsonc")
    parser.add_argument("--sqlite", type=Path, help="read a local SQLite copy instead of D1")
    parser.add_argument("--dry-run", action="store_true", help="read and check everything, write nothing")
    args = parser.parse_args()

    db: Database = SqliteDatabase(args.sqlite) if args.sqlite else WranglerD1(args.d1, args.config)
    source = d1_counts(db)
    print(f"D1: {sum(source['status'].values())} jobs, {len(source['company'])} companies, "
          f"levels {dict(source['level'])}")

    if args.dry_run:
        read, _ = copy_jobs(db, None)
        print(f"Dry run: {read} jobs read and converted, nothing written.")
        return 0

    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise SystemExit("set SUPABASE_DB_URL")
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as pg:
        read, batches = copy_jobs(db, pg)
        copy_bookkeeping(db, pg)
        problems = differences(source, pg_counts(pg))
    print(f"Copied {read} jobs in {batches} batches.")
    if problems:
        print("Counts differ (if the pipeline ran meanwhile, run again):", *problems[:50], sep="\n  ")
        return 1
    print("Counts match D1 by status, level and company.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
