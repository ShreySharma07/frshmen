"""FastAPI app serving the job board's data. Read-only: the pipeline is the only writer.

D1 free tier reads 5M rows/day, so every list query goes through idx_jobs_feed
(status, role_match, level, first_seen_at) and pages with LIMIT/OFFSET.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import traceback

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from storage import D1Database, Database

LIST_COLUMNS = (
    "id, company, title, url, location_raw, location_type, countries, cities, posted_at, first_seen_at, "
    "level, level_confidence, level_reason, yoe_min, yoe_max, yoe_evidence, batch_years, role_family, "
    "visa_sponsorship, eligible, evidence"
)
# Which evidence decides a label, in order of preference. The page shows this one line per job.
HIGHLIGHT_KINDS = {
    "fresher": ("batch", "fresher_text", "yoe_required", "fresher_title"),  # batch says who can apply
    "maybe": ("yoe_required", "yoe_preferred", "batch"),
    "experienced": ("yoe_required", "senior_title"),
}
HIGHLIGHT_MAX = 280
JSON_COLUMNS = ("countries", "cities", "batch_years", "evidence", "skills")
# The page's Role filter; plain SWE roles that passed the Python + AI/ML check count as AI/ML.
FAMILIES = {"ai_ml": ("ai_ml", "generic_swe"), "backend": ("backend",), "mobile": ("mobile",)}
# Every view shows only roles whose location fits the profile, unless asked otherwise.
ELIGIBLE = "eligible = 1"
# Postings older than this are hidden when the source gives a posting date (docs/decisions.md);
# jobs without one stay, since nothing says they're old.
MAX_POST_AGE_DAYS = 30
FRESH = "(posted_at IS NULL OR posted_at >= ?)"
# What every page count and list starts from: open target roles that fit the profile and aren't stale.
SHOWN = f"status = 'open' AND role_match = 1 AND {ELIGIBLE} AND {FRESH}"
# D1 rejects LIKE patterns over 50 bytes.
MAX_QUERY_CHARS = 40


def get_db(request: Request) -> Database:
    env = request.scope.get("env")
    if env is not None and hasattr(env, "DB"):
        return D1Database(env.DB)
    return request.app.state.db


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    for col in JSON_COLUMNS:
        if isinstance(row.get(col), str):
            try:
                row[col] = json.loads(row[col])
            except json.JSONDecodeError:
                pass
    for col in ("role_match", "eligible"):
        if col in row:
            row[col] = bool(row[col])
    return row


def _highlight(row: dict[str, Any]) -> dict[str, str] | None:
    """The one snippet that best explains the label, so the list can show it without the full evidence."""
    items = (row.get("evidence") or {}).get("level", []) if isinstance(row.get("evidence"), dict) else []
    for kind in HIGHLIGHT_KINDS.get(row.get("level", ""), ()):
        for item in items:
            if item.get("kind") == kind and item.get("snippet"):
                text = item["snippet"]
                return {"kind": kind, "text": text if len(text) <= HIGHLIGHT_MAX else text[: HIGHLIGHT_MAX - 1] + "…"}
    return None


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    row = _decode(row)
    row["highlight"] = _highlight(row)
    row.pop("evidence", None)
    return row


def _since(hours: int) -> str:
    t = datetime.now(timezone.utc) - timedelta(hours=hours)
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def create_app() -> FastAPI:
    app = FastAPI(title="frshmen", docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.exception_handler(Exception)
    async def report_errors(request: Request, exc: Exception) -> JSONResponse:
        # Printed tracebacks land in Workers Logs; the short type/message makes a failure
        # diagnosable from the browser. Nothing secret flows through this read-only API.
        traceback.print_exc()
        return JSONResponse({"error": f"{type(exc).__name__}: {str(exc)[:300]}"}, status_code=500)

    @app.get("/api/jobs")
    async def list_jobs(
        view: Literal["fresher", "maybe", "new", "all"] = "fresher",
        # Newer, independent filters; when given they replace `view`.
        level: Literal["fresher", "maybe", "any"] | None = None,
        # Experience bucket from the page: "fresher", "0-1".."0-5" (fresher, or a stated minimum within
        # that many years), "unstated" (no number in the posting), or "all". Replaces `level` when given.
        experience: Literal["fresher", "0-1", "0-2", "0-3", "0-5", "unstated", "all"] | None = None,
        posted: Literal["any", "24h"] | None = None,
        role: Literal["target", "all"] = "target",
        q: str | None = Query(None, max_length=100),
        company: str | None = None,
        location_type: Literal["remote", "hybrid", "onsite"] | None = None,
        country: str | None = Query(None, max_length=60),
        city: str | None = Query(None, max_length=60),
        family: Literal["ai_ml", "backend", "mobile"] | None = None,
        include_ineligible: bool = False,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=5000),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        where = ["status = 'open'", FRESH]
        params: list[Any] = [_since(MAX_POST_AGE_DAYS * 24)]
        if role == "target":
            where.append("role_match = 1")
        if not include_ineligible:
            where.append(ELIGIBLE)
        if family:
            fams = FAMILIES[family]
            where.append(f"role_family IN ({', '.join('?' * len(fams))})")
            params += list(fams)
        if level is None and posted is None:
            # Legacy `view`: "new" was fresher + maybe seen in the last 24 hours.
            level = {"fresher": "fresher", "maybe": "maybe", "new": "any"}.get(view)
            posted = "24h" if view == "new" else "any"
        if experience is not None:
            level = None
            if experience == "fresher":
                where.append("level = 'fresher'")
            elif experience == "unstated":
                where.append("level != 'fresher' AND yoe_min IS NULL")
            elif experience.startswith("0-"):
                where.append("(level = 'fresher' OR (yoe_min IS NOT NULL AND yoe_min <= ?))")
                params.append(int(experience[2:]))
        if level in ("fresher", "maybe"):
            where.append("level = ?")
            params.append(level)
        elif level == "any":
            where.append("level IN ('fresher', 'maybe')")
        if posted == "24h":
            # "New" means new to us (first_seen_at); many sources have no reliable post date.
            where.append("first_seen_at >= ?")
            params.append(_since(24))
        if company:
            where.append("company = ?")
            params.append(company)
        if location_type:
            where.append("location_type = ?")
            params.append(location_type)
        if country:
            # countries is a JSON array; json_each matches whole names ("India", not "Indiana").
            where.append("EXISTS (SELECT 1 FROM json_each(jobs.countries) AS c WHERE c.value = ?)")
            params.append(country)
        if city:
            where.append("EXISTS (SELECT 1 FROM json_each(jobs.cities) AS c WHERE c.value = ?)")
            params.append(city)
        if q and q.strip():
            pattern = f"%{q.strip()[:MAX_QUERY_CHARS]}%"
            where.append("(title LIKE ? OR company LIKE ?)")
            params += [pattern, pattern]
        sql = (f"SELECT {LIST_COLUMNS} FROM jobs WHERE {' AND '.join(where)} "
               # Newest posting first; first-seen time stands in where the source gives no date.
               "ORDER BY COALESCE(posted_at, first_seen_at) DESC, id LIMIT ? OFFSET ?")
        rows = await db.all(sql, [*params, limit + 1, offset])
        return {
            "jobs": [_summary(r) for r in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    @app.get("/api/jobs/{job_id:path}")
    async def get_job(job_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
        rows = await db.all("SELECT * FROM jobs WHERE id = ?", [job_id])
        if not rows:
            raise HTTPException(status_code=404, detail="job not found")
        return _decode(rows[0])

    @app.get("/api/meta")
    async def meta(db: Database = Depends(get_db)) -> dict[str, Any]:
        cutoff = [_since(MAX_POST_AGE_DAYS * 24)]
        listed = f"{SHOWN} AND level IN ('fresher', 'maybe')"
        counts = await db.all(f"SELECT level, COUNT(*) AS n FROM jobs WHERE {SHOWN} GROUP BY level", cutoff)
        new = await db.all(f"SELECT COUNT(*) AS n FROM jobs WHERE {listed} AND first_seen_at >= ?", [*cutoff, _since(24)])
        companies = await db.all(
            f"SELECT company, COUNT(*) AS n FROM jobs WHERE {listed} GROUP BY company ORDER BY company", cutoff
        )
        countries = await db.all(
            f"SELECT c.value AS country, COUNT(*) AS n FROM jobs, json_each(jobs.countries) AS c WHERE {listed} "
            "GROUP BY c.value ORDER BY n DESC, c.value", cutoff
        )
        cities = await db.all(
            f"SELECT c.value AS city, COUNT(*) AS n FROM jobs, json_each(jobs.cities) AS c WHERE {listed} "
            "GROUP BY c.value ORDER BY n DESC, c.value", cutoff
        )
        families = await db.all(
            f"SELECT role_family AS family, COUNT(*) AS n FROM jobs WHERE {listed} GROUP BY role_family", cutoff
        )
        last_run = await db.all("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
        by_level = {r["level"]: r["n"] for r in counts}
        return {
            "counts": {
                "fresher": by_level.get("fresher", 0),
                "maybe": by_level.get("maybe", 0),
                "experienced": by_level.get("experienced", 0),
                "new": new[0]["n"] if new else 0,
            },
            "companies": companies,
            "countries": countries,
            "cities": cities,
            "families": {
                name: sum(f["n"] for f in families if f["family"] in members) for name, members in FAMILIES.items()
            },
            "last_run": _decode(last_run[0]) if last_run else None,
        }

    return app
