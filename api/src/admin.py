"""/api/admin: numbers for the person running Aventra (docs/decisions.md, 2026-11-13).

Only accounts in the admins table (db/postgres/0011_admins.sql) get in: a signed-in student
gets 403, which says no more than that the page exists (it is unlinked).
"""

from __future__ import annotations

import json
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response

from auth import current_user
from pg_queries import BANDS, OPEN
from storage import Database

RUNS_SHOWN = 10
SIGNUP_DAYS = 14
ERRORS_SHOWN = 30


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def router(get_db: Callable[..., Any]) -> APIRouter:
    r = APIRouter(prefix="/api/admin")

    async def require_admin(uid: str = Depends(current_user), db: Database = Depends(get_db)) -> str:
        if not await db.all("SELECT 1 FROM admins WHERE user_id = $1", [uid]):
            raise HTTPException(status_code=403, detail="admins only")
        return uid

    @r.get("/overview")
    async def overview(response: Response, _: str = Depends(require_admin), db: Database = Depends(get_db)) -> dict[str, Any]:
        # Live numbers for one person: never kept by the browser or Cloudflare's cache.
        response.headers["Cache-Control"] = "no-store"
        bands = ", ".join(f"'{b}', COUNT(*) FILTER (WHERE {sql})" for b, sql in BANDS.items())
        jobs = (await db.all(
            f"SELECT COUNT(*) AS open, COUNT(*) FILTER (WHERE first_seen_at > now() - interval '24 hours') AS new_24h, "
            f"jsonb_build_object({bands})::text AS bands FROM job_cards WHERE {OPEN}"))[0]
        by_source = await db.all(f"SELECT source, COUNT(*) AS n FROM job_cards WHERE {OPEN} GROUP BY 1 ORDER BY 2 DESC")
        by_category = await db.all(f"SELECT category, COUNT(*) AS n FROM job_cards WHERE {OPEN} AND category IS NOT NULL "
                                   "GROUP BY 1 ORDER BY 2 DESC")
        runs = await db.all(
            "SELECT finished_at, companies_ok, companies_failed, jobs_seen, jobs_new, jobs_changed, jobs_closed, "
            "errors::text AS errors FROM runs ORDER BY id DESC LIMIT $1", [RUNS_SHOWN])
        latest_errors = (_json(runs[0]["errors"]) or {}) if runs else {}
        users = (await db.all("SELECT COUNT(*) AS total FROM students"))[0]
        signups = await db.all(
            "SELECT d::date AS day, COUNT(s.id) AS n "
            "FROM generate_series(current_date - $1::int + 1, current_date, interval '1 day') d "
            "LEFT JOIN students s ON s.created_at::date = d::date GROUP BY 1 ORDER BY 1", [SIGNUP_DAYS])
        usage = (await db.all(
            "SELECT (SELECT COUNT(*) FROM fit_checks WHERE created_at > now() - interval '24 hours') AS fit_checks, "
            "(SELECT COUNT(*) FROM tailored_resumes WHERE created_at > now() - interval '24 hours') AS tailored_resumes"))[0]
        return {
            "jobs": {
                "open": int(jobs["open"]), "new_24h": int(jobs["new_24h"]), "bands": _json(jobs["bands"]),
                "by_source": [{"source": x["source"], "n": int(x["n"])} for x in by_source],
                "by_category": {x["category"]: int(x["n"]) for x in by_category},
            },
            "pipeline": {
                "runs": [{**{k: v for k, v in run.items() if k != "errors"},
                          "error_count": len(_json(run["errors"]) or {})} for run in runs],
                "latest_errors": dict(list(latest_errors.items())[:ERRORS_SHOWN]),
            },
            "users": {
                "total": int(users["total"]),
                "signups": [{"day": str(x["day"]), "n": int(x["n"])} for x in signups],
                "usage_24h": {k: int(v) for k, v in usage.items()},
            },
        }

    return r
