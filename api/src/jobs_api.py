"""FastAPI app serving the job board's data. Read-only: the pipeline is the only writer.

The page lists every open job, newest first, 20 per page; the reader narrows it with filters
(docs/decisions.md, 2026-10-08). Reads come from Supabase Postgres through Hyperdrive
(2026-10-16): lists walk jobs_recent_idx in sort order through the job_cards view, the total
is counted only when asked for, and the filter lists come from a snapshot the pipeline writes
once per run. Hyperdrive's free tier allows 100k queries/day; a page view costs one or two.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Literal

import traceback

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import fit

from pg_queries import INTERN, META_SELECT, OPEN, ORDER_BY, ORDER_KEY
from queries import FAMILIES
from storage import Database, connect

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
JSON_COLUMNS = ("evidence", "errors")  # jsonb arrives as text; arrays arrive as lists
# The location rules (India except onsite-only Bengaluru/Hyderabad, abroad with sponsorship)
# are now a filter the reader turns on, not a hidden default.
ELIGIBLE = "eligible"
PER_PAGE = 20
MAX_QUERY_CHARS = 40
# A reposted listing's old link still opens its job (job_aliases, docs/decisions.md 2026-10-16).
RESOLVE = "COALESCE((SELECT job_id FROM job_aliases WHERE alias_id = $1), $1)"


async def get_db(request: Request) -> AsyncIterator[Database]:
    """One connection per request: Hyperdrive in the Worker, app.state.dsn locally and in tests."""
    env = request.scope.get("env")
    hyperdrive = getattr(env, "HYPERDRIVE", None) if env is not None else None
    async with connect(hyperdrive=hyperdrive, dsn=None if hyperdrive else request.app.state.dsn) as db:
        yield db


class Params(list):
    """Collects query parameters and hands back their $n placeholders."""

    def __call__(self, value: Any) -> str:
        self.append(value)
        return f"${len(self)}"


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


def fit_config(request: Request) -> tuple[str, fit.Post] | None:
    """(api_key, post) when the fit check is switched on, else None. Tests set app.state.fit."""
    override = getattr(request.app.state, "fit", None)
    if override:
        return override
    env = request.scope.get("env")
    if env is None or str(getattr(env, "FIT_CHECK", "") or "") != "on":
        return None
    key = getattr(env, "GEMINI_API_KEY", None)
    return (str(key), fit.worker_post) if key else None


def fit_check_enabled(request: Request) -> bool:
    return fit_config(request) is not None


class FitRequest(BaseModel):
    resume: str = Field(min_length=50, max_length=fit.MAX_RESUME_CHARS)


def _since(hours: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


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
        # "0-N": fresher roles plus any whose stated minimum is within N years. "unstated": no number
        # in the posting. "internship": intern/trainee/apprentice titles, whatever their label.
        experience: Literal["all", "fresher", "internship", "0-1", "0-2", "0-3", "0-5", "unstated",
                            "experienced"] = "all",
        # "target": the roles in config/profile.yaml (AI/ML, Python backend, Android/React Native).
        role: Literal["all", "target", "ai_ml", "backend", "mobile"] = "all",
        # "24h" is new to us (first seen); 7d/30d use the posting date where the source gives one.
        posted: Literal["any", "24h", "7d", "30d"] = "any",
        eligible_only: bool = False,
        q: str | None = Query(None, max_length=100),
        company: str | None = None,
        location_type: Literal["remote", "hybrid", "onsite"] | None = None,
        country: str | None = Query(None, max_length=60),
        city: str | None = Query(None, max_length=60),
        page: int = Query(1, ge=1, le=2000),
        per_page: int = Query(PER_PAGE, ge=1, le=50),
        # Counting reads every matching row, so the page asks only when the filters change.
        with_total: bool = False,
        db: Database = Depends(get_db),
    ) -> dict[str, Any]:
        where = [OPEN]
        p = Params()
        if experience == "fresher":
            where.append("level = 'fresher'")
        elif experience == "experienced":
            where.append("level = 'experienced'")
        elif experience == "unstated":
            where.append("level <> 'fresher' AND yoe_min IS NULL")
        elif experience == "internship":
            where.append(INTERN)
        elif experience.startswith("0-"):
            where.append(f"(level = 'fresher' OR (yoe_min IS NOT NULL AND yoe_min <= {p(int(experience[2:]))}))")
        if role == "target":
            where.append("role_match")
        elif role != "all":
            where.append(f"role_match AND role_family = ANY({p(list(FAMILIES[role]))})")
        if eligible_only:
            where.append(ELIGIBLE)
        if posted == "24h":
            where.append(f"first_seen_at >= {p(_since(24))}")
        elif posted in ("7d", "30d"):
            where.append(f"{ORDER_KEY} >= {p(_since(24 * int(posted[:-1])))}")
        if company:
            where.append(f"company = {p(company)}")
        if location_type:
            where.append(f"location_type = {p(location_type)}")
        if country:
            # Whole names in the array ("India", not "Indiana").
            where.append(f"{p(country)} = ANY(countries)")
        if city:
            where.append(f"{p(city)} = ANY(cities)")
        if q and q.strip():
            pattern = p(f"%{q.strip()[:MAX_QUERY_CHARS]}%")
            where.append(f"(title ILIKE {pattern} OR company ILIKE {pattern})")
        cond = " AND ".join(where)
        filters = list(p)
        offset = (page - 1) * per_page
        rows = await db.all(f"SELECT {LIST_COLUMNS} FROM job_cards WHERE {cond} {ORDER_BY} "
                            f"LIMIT {p(per_page + 1)} OFFSET {p(offset)}", p)
        body: dict[str, Any] = {
            "jobs": [_summary(r) for r in rows[:per_page]],
            "page": page,
            "per_page": per_page,
            "has_more": len(rows) > per_page,
        }
        if with_total:
            total = (await db.all(f"SELECT COUNT(*) AS n FROM job_cards WHERE {cond}", filters))[0]["n"]
            body.update(total=total, pages=max(1, -(-total // per_page)))
        return body

    @app.post("/api/jobs/{job_id:path}/fit")
    async def check_fit(job_id: str, req: FitRequest, request: Request,
                        db: Database = Depends(get_db)) -> dict[str, Any]:
        config = fit_config(request)
        if config is None:
            raise HTTPException(status_code=404, detail="fit check is turned off")
        rows = await db.all(f"SELECT title, company, description_text FROM job_cards WHERE id = {RESOLVE}", [job_id])
        if not rows:
            raise HTTPException(status_code=404, detail="job not found")
        try:
            return await fit.check(rows[0], req.resume, *config)
        except fit.FitUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from None

    @app.get("/api/jobs/{job_id:path}")
    async def get_job(job_id: str, db: Database = Depends(get_db)) -> dict[str, Any]:
        rows = await db.all(f"SELECT * FROM job_cards WHERE id = {RESOLVE}", [job_id])
        if not rows:
            raise HTTPException(status_code=404, detail="job not found")
        return _decode(rows[0])

    @app.get("/api/meta")
    async def meta(request: Request, db: Database = Depends(get_db)) -> dict[str, Any]:
        snap = await db.all("SELECT value::text AS value, updated_at FROM meta WHERE key = 'filters'")
        # Before the pipeline's first Supabase run there may be no snapshot; compute it live.
        value = snap[0]["value"] if snap else (await db.all(META_SELECT))[0]["value"]
        filters = json.loads(value)
        last_run = await db.all("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
        return {
            **filters,
            "levels": {lvl: (filters.get("levels") or {}).get(lvl, 0) for lvl in ("fresher", "maybe", "experienced")},
            "snapshot_at": snap[0]["updated_at"] if snap else None,
            "last_run": _decode(last_run[0]) if last_run else None,
            "fit_check": fit_check_enabled(request),
        }

    return app
