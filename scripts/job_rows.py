"""One fetched job (data/jobs.json) -> the rows publish_pg.py writes: jobs and job_labels.

Kept apart from the publisher so the mapping can be tested without a database.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JOBS = ROOT / "data" / "jobs.json"

# Bump when extract/ rules change so every stored job gets re-classified once.
EXTRACT_VERSION = 4  # 2: countries/location_type; 3: Indian cities; 4: mobile roles, visa, eligibility
# Real descriptions are ~5 KB; a cap keeps one malformed page from bloating the database.
MAX_DESCRIPTION_CHARS = 60_000
# Closed (never deleted) after this many runs in a row missing from a board that answered.
CLOSE_AFTER_MISSES = 2

# Fingerprinted by extract_hash: when none of these change, the label isn't rewritten.
EXTRACT_FIELDS = [
    "extract_version", "location_type", "countries", "cities", "visa_sponsorship", "eligible", "yoe_min", "yoe_max", "yoe_evidence", "batch_years", "level", "level_confidence",
    "level_reason", "role_match", "role_family", "role_reason", "evidence", "extract_hash",
]
LOCATION_TYPES = {"remote", "hybrid", "onsite"}
VISA = {"yes", "no", "unknown"}
LABEL_FIELDS = [
    "level", "level_confidence", "level_reason", "yoe_min", "yoe_max", "yoe_evidence", "batch_years",
    "role_match", "role_family", "role_reason", "location_type", "countries", "cities", "eligible",
    "visa_sponsorship", "skills", "evidence",
]


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


# --- Label rows ------------------------------------------------------------------------------

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
    """ISO text -> aware datetime; anything unparseable becomes NULL rather than failing the run."""
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
        "role_reason": r.get("role_reason"),
        "location_type": r.get("location_type") if r.get("location_type") in LOCATION_TYPES else None,
        "countries": _texts(r.get("countries")),
        "cities": _texts(r.get("cities")),
        "eligible": bool(r.get("eligible", 1)),
        "visa_sponsorship": r.get("visa_sponsorship") if r.get("visa_sponsorship") in VISA else "unknown",
        "skills": _texts(r.get("skills")),
        "evidence": _json(r.get("evidence"), None),
    }
    # to_row sets extract_hash over the same values; rows without one get a hash of what's stored.
    row["label_hash"] = r.get("extract_hash") or hashlib.sha256(
        json.dumps({k: row[k] for k in LABEL_FIELDS}, sort_keys=True, default=str).encode()).hexdigest()
    row["evidence"] = Jsonb(row["evidence"]) if row["evidence"] is not None else None
    return row


# Re-points is_current at each listed job's newest label (two statements, so the unique
# "one current label per job" index never sees two at once).
_NEWEST = "(SELECT job_id, MAX(rules_version) AS v FROM job_labels WHERE job_id = ANY(%(ids)s) GROUP BY job_id) m"
REFRESH_CURRENT = [
    f"UPDATE job_labels l SET is_current = false FROM {_NEWEST} "
    "WHERE l.job_id = m.job_id AND l.is_current AND l.rules_version <> m.v",
    f"UPDATE job_labels l SET is_current = true FROM {_NEWEST} "
    "WHERE l.job_id = m.job_id AND NOT l.is_current AND l.rules_version = m.v",
]


def refresh_current(cur: psycopg.Cursor, ids: list[str]) -> None:
    for sql in REFRESH_CURRENT:
        cur.execute(sql, {"ids": ids})
