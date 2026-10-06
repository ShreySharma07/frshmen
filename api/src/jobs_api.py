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
    "id, company, title, url, location_raw, location_type, countries, posted_at, first_seen_at, "
    "level, level_confidence, level_reason, yoe_min, yoe_max, yoe_evidence, batch_years, role_family, "
    "visa_sponsorship, evidence"
)
# Which evidence decides a label, in order of preference. The page shows this one line per job.
HIGHLIGHT_KINDS = {
    "fresher": ("batch", "fresher_text", "yoe_required", "fresher_title"),  # batch says who can apply
    "maybe": ("yoe_required", "yoe_preferred", "batch"),
    "experienced": ("yoe_required", "senior_title"),
}
HIGHLIGHT_MAX = 280
JSON_COLUMNS = ("countries", "batch_years", "evidence", "skills")
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
    if "role_match" in row:
        row["role_match"] = bool(row["role_match"])
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
        role: Literal["target", "all"] = "target",
        q: str | None = Query(None, max_length=100),
        company: str | None = None,
        location_type: Literal["remote", "hybrid", "onsite"] | None = None,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=5000),
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        where = ["status = 'open'"]
        params: list[Any] = []
        if role == "target":
            where.append("role_match = 1")
        if view in ("fresher", "maybe"):
            where.append("level = ?")
            params.append(view)
        elif view == "new":
            # "New" means new to us (first_seen_at); many sources have no reliable post date.
            where.append("level IN ('fresher', 'maybe') AND first_seen_at >= ?")
            params.append(_since(24))
        if company:
            where.append("company = ?")
            params.append(company)
        if location_type:
            where.append("location_type = ?")
            params.append(location_type)
        if q and q.strip():
            pattern = f"%{q.strip()[:MAX_QUERY_CHARS]}%"
            where.append("(title LIKE ? OR company LIKE ?)")
            params += [pattern, pattern]
        sql = (f"SELECT {LIST_COLUMNS} FROM jobs WHERE {' AND '.join(where)} "
               "ORDER BY first_seen_at DESC, id LIMIT ? OFFSET ?")
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
        counts = await db.all(
            "SELECT level, COUNT(*) AS n FROM jobs WHERE status = 'open' AND role_match = 1 GROUP BY level"
        )
        new = await db.all(
            "SELECT COUNT(*) AS n FROM jobs WHERE status = 'open' AND role_match = 1 "
            "AND level IN ('fresher', 'maybe') AND first_seen_at >= ?",
            [_since(24)],
        )
        companies = await db.all(
            "SELECT company, COUNT(*) AS n FROM jobs WHERE status = 'open' AND role_match = 1 "
            "AND level IN ('fresher', 'maybe') GROUP BY company ORDER BY company"
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
            "last_run": _decode(last_run[0]) if last_run else None,
        }

    return app
