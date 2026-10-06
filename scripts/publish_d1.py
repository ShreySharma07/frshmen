"""Sync data/jobs.json into the jobs database, writing only what changed.

Rules (skills.md §4):
- new id            -> INSERT, first_seen_at = now (never overwritten later)
- content changed   -> UPDATE text + extraction fields (content_hash differs)
- extraction changed -> UPDATE extraction fields, only when the extracted values differ
                       (extract_hash), so a rule change rewrites only the jobs it affects
- closed but back   -> reopen
- open but missing from a board that fetched OK -> missed_runs + 1; closed (never deleted)
  after CLOSE_AFTER_MISSES runs in a row, so one flaky response doesn't hide a live job

D1's free tier allows 100k written rows/day (index updates count too), so unchanged
jobs are not touched and each run writes at most MAX_ROWS_WRITTEN_PER_RUN rows: new
jobs first, then changed and reopened ones, then re-extracted ones, then closings.
Whatever doesn't fit is picked up by the next run.
Writes go out as one SQL file through `wrangler d1 execute`, because D1 caps a
query at 100 bound parameters and per-row API calls would take thousands of requests.

Run:
  python scripts/publish_d1.py --sqlite data/local.db          # local dev database
  python scripts/publish_d1.py --d1 frshmen                    # Cloudflare D1 (needs wrangler + token)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JOBS = ROOT / "data" / "jobs.json"
MIGRATIONS = ROOT / "db" / "migrations"

# Bump when extract/ rules change so every stored job gets re-classified once.
EXTRACT_VERSION = 4  # 2: countries/location_type; 3: Indian cities; 4: mobile roles, visa, eligibility
# D1 rejects SQL statements over 100 KB; real descriptions are ~5 KB.
MAX_DESCRIPTION_CHARS = 60_000
CLOSE_AFTER_MISSES = 2
# 8 scheduled runs a day x 12k stays under D1's 100k rows written/day even if every run is busy.
MAX_ROWS_WRITTEN_PER_RUN = 12_000
# Rows D1 counts per statement kind: the row itself, plus idx_jobs_feed when an indexed column moves.
COST_INDEXED, COST_PLAIN = 2, 1

TEXT_FIELDS = [
    "source", "company", "company_slug", "title", "url", "location_raw",
    "department", "employment_type", "posted_at", "description_text", "content_hash",
]
EXTRACT_FIELDS = [
    "extract_version", "location_type", "countries", "cities", "visa_sponsorship", "eligible", "yoe_min", "yoe_max", "yoe_evidence", "batch_years", "level", "level_confidence",
    "level_reason", "role_match", "role_family", "role_reason", "evidence", "extract_hash",
]


class Database(Protocol):
    def query(self, sql: str) -> list[dict[str, Any]]: ...
    def execute_script(self, sql: str) -> None: ...
    def migrate(self) -> None: ...


class SqliteDatabase:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row

    def query(self, sql: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(sql).fetchall()]

    def execute_script(self, sql: str) -> None:
        self.conn.executescript(sql)
        self.conn.commit()

    def migrate(self) -> None:
        # Tracks applied files like wrangler does in D1, so ALTER TABLEs run exactly once.
        self.conn.execute("CREATE TABLE IF NOT EXISTS local_migrations (name TEXT PRIMARY KEY)")
        applied = {r[0] for r in self.conn.execute("SELECT name FROM local_migrations")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name not in applied:
                self.execute_script(path.read_text() + f"\nINSERT INTO local_migrations VALUES ('{path.name}');")


class WranglerD1:
    """Talks to Cloudflare D1 through the wrangler CLI (auth via CLOUDFLARE_API_TOKEN / ACCOUNT_ID)."""

    def __init__(self, database: str, config: Path):
        self.database = database
        self.config = config
        self.wrangler = ["npx", "--yes", "wrangler@4"]
        if not shutil.which("npx"):
            raise SystemExit("npx not found: install Node.js to publish to D1")

    def _run(self, *args: str) -> str:
        return self._wrangler("execute", self.database, "--remote", *args)

    def _wrangler(self, *args: str) -> str:
        cmd = [*self.wrangler, "d1", *args, "--config", str(self.config)]
        out = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return out.stdout

    def migrate(self) -> None:
        # wrangler records applied migrations in D1, so later ALTER TABLEs run exactly once.
        self._wrangler("migrations", "apply", self.database, "--remote")

    def query(self, sql: str) -> list[dict[str, Any]]:
        payload = json.loads(self._run("--command", sql, "--json"))
        return [row for block in payload for row in block.get("results", [])]

    def execute_script(self, sql: str) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
            f.write(sql)
        self._run("--file", f.name, "--yes")


@dataclass
class Plan:
    sql: str
    new: int
    changed: int
    reclassified: int
    reopened: int
    closed: int
    missed: int = 0  # absent once, still open
    deferred: int = 0  # writes left for the next run (daily D1 budget)
    rows_written: int = 0  # D1 rows this plan writes, index updates included (estimate)


def sql_literal(value: Any) -> str:
    """Render a value as a SQLite literal. Only our own pipeline data reaches here."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value).replace("\x00", "")
    return "'" + text.replace("'", "''") + "'"


def extract_hash(row: dict[str, Any]) -> str:
    """Fingerprint of the extracted values, so re-extraction only writes jobs whose results changed."""
    values = {c: row.get(c) for c in EXTRACT_FIELDS if c not in ("extract_version", "extract_hash")}
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def to_row(job: dict[str, Any]) -> dict[str, Any]:
    """Map a jobs.json record onto table columns."""
    row = _row(job)
    row["extract_hash"] = extract_hash(row)
    return row


def _row(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job["id"],
        "source": job["source"],
        "company": job["company"],
        "company_slug": job["company_slug"],
        "title": job["title"],
        "url": job["url"],
        "location_raw": job.get("location_raw"),
        # Older jobs.json files predate extract/location.py; fall back to the ATS hints.
        "location_type": job.get("location_type", job.get("ats_workplace_type")),
        "countries": job.get("countries", job.get("ats_countries") or []),
        "cities": job.get("cities") or [],
        "visa_sponsorship": job.get("visa_sponsorship") or "unknown",
        # Older jobs.json files predate extract/eligibility.py: keep them visible.
        "eligible": job.get("eligible", True),
        "department": job.get("department"),
        "employment_type": job.get("employment_type"),
        "posted_at": job.get("posted_at"),
        "description_text": (job.get("description_text") or "")[:MAX_DESCRIPTION_CHARS],
        "content_hash": job["content_hash"],
        "extract_version": EXTRACT_VERSION,
        "yoe_min": job.get("yoe_min"),
        "yoe_max": job.get("yoe_max"),
        "yoe_evidence": job.get("yoe_evidence"),
        "batch_years": job.get("batch_years") or [],
        "level": job["level"],
        "level_confidence": job.get("level_confidence"),
        "level_reason": job.get("reason"),
        "role_match": bool(job.get("role_match")),
        "role_family": job.get("role_family"),
        "role_reason": job.get("role_reason"),
        "evidence": {"level": job.get("evidence") or [], "role": job.get("role_evidence") or [],
                     "location": job.get("location_evidence") or [],
                     "eligibility": job.get("eligibility_reason")},
    }


def plan(jobs: list[dict[str, Any]], boards_ok: list[dict[str, str]], existing: list[dict[str, Any]],
         now: str, budget: int = MAX_ROWS_WRITTEN_PER_RUN) -> Plan:
    current = {row["id"]: row for row in existing}
    counts = dict(new=0, changed=0, reclassified=0, reopened=0, closed=0, missed=0)
    # (priority, cost, counter, statement); lower priority numbers are written first.
    work: list[tuple[int, int, str | None, str]] = []

    for job in jobs:
        row = to_row(job)
        old = current.get(row["id"])
        if old is None:
            cols = ["id", *TEXT_FIELDS, *EXTRACT_FIELDS, "first_seen_at", "status"]
            vals = [row.get(c) for c in cols[:-2]] + [now, "open"]
            work.append((0, COST_INDEXED, "new",
                         f"INSERT INTO jobs ({', '.join(cols)}) VALUES ({', '.join(map(sql_literal, vals))});"))
            continue
        fields: list[str] = []
        counter, priority = None, 1
        if old["content_hash"] != row["content_hash"]:
            fields, counter = TEXT_FIELDS + EXTRACT_FIELDS, "changed"
        elif _extraction_changed(old, row):
            fields, counter, priority = EXTRACT_FIELDS, "reclassified", 2
        reopen = old["status"] != "open"
        if reopen:
            counter, priority = counter or "reopened", 1
        if fields or reopen or old.get("missed_runs"):
            sets = [f"{c} = {sql_literal(row[c])}" for c in fields] + ["status = 'open'", "missed_runs = 0"]
            cost = COST_INDEXED if fields or reopen else COST_PLAIN
            work.append((priority, cost, counter, f"UPDATE jobs SET {', '.join(sets)} WHERE id = {sql_literal(row['id'])};"))

    # Only close jobs from boards we actually fetched: a failed board says nothing about its jobs.
    seen = {job["id"] for job in jobs}
    ok = {(b["source"], b["company_slug"]) for b in boards_ok}
    for r in existing:
        if r["status"] != "open" or r["id"] in seen or (r["source"], r["company_slug"]) not in ok:
            continue
        if (r.get("missed_runs") or 0) + 1 >= CLOSE_AFTER_MISSES:
            work.append((3, COST_INDEXED, "closed", "UPDATE jobs SET status = 'closed', missed_runs = missed_runs + 1 "
                                                    f"WHERE id = {sql_literal(r['id'])};"))
        else:
            work.append((3, COST_PLAIN, "missed", f"UPDATE jobs SET missed_runs = missed_runs + 1 WHERE id = {sql_literal(r['id'])};"))

    stmts: list[str] = []
    spent = deferred = 0
    for _, cost, counter, stmt in sorted(work, key=lambda w: w[0]):  # stable: input order within a priority
        if spent + cost > budget:
            deferred += 1
            continue
        stmts.append(stmt)
        spent += cost
        if counter:
            counts[counter] += 1
    return Plan(sql="\n".join(stmts), deferred=deferred, rows_written=spent, **counts)


def _extraction_changed(old: dict[str, Any], row: dict[str, Any]) -> bool:
    if old.get("extract_hash"):
        return old["extract_hash"] != row["extract_hash"]
    # Rows stored before extract_hash existed: fall back to the version, as before.
    return old["extract_version"] != EXTRACT_VERSION


def run_row(p: Plan, payload: dict[str, Any], now: str) -> str:
    values = [now, len(payload.get("boards_ok", [])), len(payload.get("errors", {})), len(payload["jobs"]),
              p.new, p.changed, p.closed, payload.get("errors", {})]
    return ("INSERT INTO runs (finished_at, companies_ok, companies_failed, jobs_seen, jobs_new, jobs_changed, "
            f"jobs_closed, errors) VALUES ({', '.join(map(sql_literal, values))});")


def publish(db: Database, payload: dict[str, Any], now: str | None = None) -> Plan:
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    db.migrate()
    existing = db.query("SELECT id, source, company_slug, content_hash, extract_version, extract_hash, status, "
                        "missed_runs FROM jobs")
    p = plan(payload["jobs"], payload.get("boards_ok", []), existing, now)
    db.execute_script("\n".join(s for s in [p.sql, run_row(p, payload, now)] if s))
    return p


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--sqlite", type=Path, help="local SQLite file (created if missing)")
    target.add_argument("--d1", metavar="NAME", help="Cloudflare D1 database name, e.g. frshmen")
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--config", type=Path, default=ROOT / "api" / "wrangler.jsonc")
    args = parser.parse_args()

    payload = json.loads(args.jobs.read_text())
    db: Database = SqliteDatabase(args.sqlite) if args.sqlite else WranglerD1(args.d1, args.config)
    p = publish(db, payload)
    print(f"published: new={p.new} changed={p.changed} reclassified={p.reclassified} "
          f"reopened={p.reopened} missed_once={p.missed} closed={p.closed} (unchanged jobs not written); "
          f"~{p.rows_written} rows written, {p.deferred} writes deferred to the next run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
