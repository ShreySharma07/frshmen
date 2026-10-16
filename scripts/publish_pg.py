"""Sync data/jobs.json into Supabase Postgres, writing only what changed.

Rules (skills.md §4), on the multi-user schema (db/postgres/):
- new id            -> INSERT, first_seen_at = now (never overwritten later)
- content changed   -> UPDATE the posting (content_hash differs)
- labels changed    -> new job_labels row, only when label_hash differs; the current and the
                       previous label per job are kept, older ones dropped
- closed but back   -> reopen
- open but missing from a board that fetched OK -> missed_runs + 1; closed after
  CLOSE_AFTER_MISSES runs in a row (never deleted)

Reposts (docs/decisions.md, 2026-10-16): a new id with the same company + normalised title +
location as a stored job (repost_key) and a near-identical description is the same role
re-listed. It's recorded in job_aliases and written onto the original row, so the role keeps
one card, its applications and its first_seen_at, and shows the new listing's date.

The whole run is one transaction: a failure leaves Supabase as it was, and the next run (all
upserts) picks everything up again.

Run:
  SUPABASE_DB_URL=postgresql://... python scripts/publish_pg.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from job_rows import CLOSE_AFTER_MISSES, DEFAULT_JOBS, _ts, label_row, refresh_current, to_row  # noqa: E402

sys.path.insert(0, str(ROOT / "api" / "src"))  # SQL shared with the API
from pg_queries import SNAPSHOT  # noqa: E402

KEEP_LABELS = 2  # current + previous, enough to check a rules update for regressions
SAME_TEXT = 0.9  # shingle overlap above which two descriptions are the same posting
_SHINGLE = 5


# --- Reposts ---------------------------------------------------------------------------------

def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def repost_key(company: str, title: str, location: str | None) -> str:
    return hashlib.sha256("\x1f".join([_norm(company), _norm(title), _norm(location)]).encode()).hexdigest()


def _shingles(text: str | None) -> set[tuple[str, ...]]:
    words = _norm(text).split()
    return {tuple(words[i:i + _SHINGLE]) for i in range(max(len(words) - _SHINGLE + 1, 1))} if words else set()


def same_posting(a: str | None, b: str | None) -> bool:
    """Near-identical descriptions. Empty text never matches: no evidence, no merge."""
    sa, sb = _shingles(a), _shingles(b)
    return bool(sa and sb) and len(sa & sb) / len(sa | sb) >= SAME_TEXT


def resolve(rows: list[dict[str, Any]], known: set[str], aliases: dict[str, str],
            candidates: dict[str, list[tuple[str, str | None]]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Map fetched rows onto stored job ids.

    Returns (canonical id -> the row to write there, new aliases {alias id: job id}). When two
    fetched listings land on one job, the newer posting date wins.
    """
    out: dict[str, dict[str, Any]] = {}
    new_aliases: dict[str, str] = {}
    for row in rows:
        target = aliases.get(row["id"], row["id"])
        if target not in known and row["id"] not in aliases:
            for cand_id, cand_text in candidates.get(row["repost_key"], []):
                if cand_id != row["id"] and same_posting(row["description_text"], cand_text):
                    target = new_aliases[row["id"]] = cand_id
                    break
        prev = out.get(target)
        if prev is None or (row.get("posted_at") or "") > (prev.get("posted_at") or ""):
            out[target] = row
    return out, new_aliases


def board_prefixes(boards_ok: list[dict[str, str]]) -> tuple[str, ...]:
    # Job ids are "<source>:<board>:<external id>", so a board's jobs share this prefix.
    return tuple(f"{b['source']}:{b['company_slug']}:" for b in boards_ok)


# --- Writing ---------------------------------------------------------------------------------

UPSERT_JOB = """
INSERT INTO jobs (id, company_id, source, title, url, location_raw, department, employment_type,
                  posted_at, first_seen_at, status, missed_runs, description_text, content_hash, repost_key)
VALUES (%(id)s, %(company_id)s, %(source)s, %(title)s, %(url)s, %(location_raw)s, %(department)s,
        %(employment_type)s, %(posted_at)s, %(now)s, 'open', 0, %(description_text)s, %(content_hash)s,
        %(repost_key)s)
ON CONFLICT (id) DO UPDATE SET
  company_id = EXCLUDED.company_id, source = EXCLUDED.source, title = EXCLUDED.title, url = EXCLUDED.url,
  location_raw = EXCLUDED.location_raw, department = EXCLUDED.department,
  employment_type = EXCLUDED.employment_type, posted_at = EXCLUDED.posted_at,
  description_text = EXCLUDED.description_text, content_hash = EXCLUDED.content_hash,
  repost_key = EXCLUDED.repost_key, status = 'open', missed_runs = 0
"""

_LFIELDS = ["level", "level_confidence", "level_reason", "yoe_min", "yoe_max", "yoe_evidence", "batch_years",
            "role_match", "role_family", "role_reason", "location_type", "countries", "cities", "eligible",
            "visa_sponsorship", "skills", "evidence"]
_LCOLS = ["job_id", "rules_version", "label_hash", *_LFIELDS]
UPSERT_LABEL = f"""
INSERT INTO job_labels ({", ".join(_LCOLS)}) VALUES ({", ".join(f"%({c})s" for c in _LCOLS)})
ON CONFLICT (job_id, rules_version) DO UPDATE SET
  {", ".join(f"{c} = EXCLUDED.{c}" for c in ["label_hash", *_LFIELDS])}, labelled_at = now()
"""

PRUNE_LABELS = """
DELETE FROM job_labels l USING (
  SELECT job_id, rules_version, row_number() OVER (PARTITION BY job_id ORDER BY rules_version DESC) AS rn
  FROM job_labels WHERE job_id = ANY(%s)) old
WHERE l.job_id = old.job_id AND l.rules_version = old.rules_version AND old.rn > %s
"""


def publish(pg: psycopg.Connection, payload: dict[str, Any], now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    rows = [to_row(j) for j in payload["jobs"]]
    for r in rows:
        r["repost_key"] = repost_key(r["company"], r["title"], r["location_raw"])
    counts = dict(new=0, changed=0, reclassified=0, reopened=0, reposts=0, missed=0, closed=0)

    with pg.transaction(), pg.cursor() as cur:
        cur.execute("SELECT id, status, missed_runs, content_hash, repost_key, url, posted_at FROM jobs")
        existing = {r[0]: r for r in cur.fetchall()}
        cur.execute("SELECT job_id, label_hash FROM current_labels")
        labels = dict(cur.fetchall())
        cur.execute("SELECT alias_id, job_id FROM job_aliases")
        aliases = dict(cur.fetchall())

        unknown_keys = sorted({r["repost_key"] for r in rows if r["id"] not in existing and r["id"] not in aliases})
        candidates: dict[str, list[tuple[str, str | None]]] = {}
        if unknown_keys:
            cur.execute("SELECT repost_key, id, description_text FROM jobs WHERE repost_key = ANY(%s) "
                        "ORDER BY first_seen_at", (unknown_keys,))
            for key, jid, text in cur.fetchall():
                candidates.setdefault(key, []).append((jid, text))
        targets, new_aliases = resolve(rows, set(existing), aliases, candidates)
        counts["reposts"] = len(new_aliases)

        names = sorted({r["company"] for r in targets.values()})
        cur.executemany("INSERT INTO companies (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", [(n,) for n in names])
        cur.execute("SELECT name, id FROM companies WHERE name = ANY(%s)", (names,))
        company_ids = dict(cur.fetchall())

        job_writes, label_writes = [], []
        for jid, r in targets.items():
            old = existing.get(jid)
            if old is None:
                counts["new"] += 1
            elif old[3] != r["content_hash"]:
                counts["changed"] += 1
            elif old[1] != "open":
                counts["reopened"] += 1
            posted = _ts(r.get("posted_at"))
            # url and posted_at matter on their own: a repost keeps the text but brings a new link and date.
            if old is None or old[1:] != ("open", 0, r["content_hash"], r["repost_key"], r["url"], posted):
                job_writes.append({**r, "id": jid, "company_id": company_ids[r["company"]], "now": now,
                                   "posted_at": posted})
            label = label_row({**r, "id": jid})
            if labels.get(jid) != label["label_hash"]:
                if old is not None and jid in labels:
                    counts["reclassified"] += 1
                label_writes.append(label)
        cur.executemany(UPSERT_JOB, job_writes)
        cur.executemany(UPSERT_LABEL, label_writes)
        if label_writes:
            relabelled = [lw["job_id"] for lw in label_writes]
            cur.execute(PRUNE_LABELS, (relabelled, KEEP_LABELS))
            refresh_current(cur, relabelled)
        cur.executemany("INSERT INTO job_aliases (alias_id, job_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        list(new_aliases.items()))

        # Only jobs from boards fetched OK this run: a failed board says nothing about its jobs.
        prefixes = board_prefixes(payload.get("boards_ok", []))
        missing = [(jid, old[2]) for jid, old in existing.items()
                   if old[1] == "open" and jid not in targets and jid.startswith(prefixes)] if prefixes else []
        close = [jid for jid, missed in missing if missed + 1 >= CLOSE_AFTER_MISSES]
        miss = [jid for jid, missed in missing if missed + 1 < CLOSE_AFTER_MISSES]
        cur.execute("UPDATE jobs SET status = 'closed', missed_runs = missed_runs + 1 WHERE id = ANY(%s)", (close,))
        cur.execute("UPDATE jobs SET missed_runs = missed_runs + 1 WHERE id = ANY(%s)", (miss,))
        counts["closed"], counts["missed"] = len(close), len(miss)

        cur.execute(
            "INSERT INTO runs (finished_at, companies_ok, companies_failed, jobs_seen, jobs_new, jobs_changed, "
            "jobs_closed, errors) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (now, len(payload.get("boards_ok", [])), len(payload.get("errors", {})), len(payload["jobs"]),
             counts["new"], counts["changed"], counts["closed"], Jsonb(payload.get("errors", {}))))
        # Last, so the page's filter counts include this run's writes.
        cur.execute(SNAPSHOT)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    args = parser.parse_args()
    url = os.environ.get("SUPABASE_DB_URL") or sys.exit("set SUPABASE_DB_URL")
    payload = json.loads(args.jobs.read_text())
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as pg:
        counts = publish(pg, payload)
    print("published to Supabase: " + " ".join(f"{k}={v}" for k, v in counts.items()) + " (unchanged jobs not written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
