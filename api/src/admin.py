"""/api/admin: numbers for the person running Aventra (docs/decisions.md, 2026-11-13).

Only accounts in the admins table (db/postgres/0011_admins.sql) get in: a signed-in student
gets 403, which says no more than that the page exists (it is unlinked).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from auth import current_user
from contacts_csv import ALIASES, parse
from pg_queries import BANDS, OPEN
from storage import Database

RUNS_SHOWN = 10
SIGNUP_DAYS = 14
ERRORS_SHOWN = 30


class ManualJob(BaseModel):
    """A job typed in by an admin. Limits match db/postgres/0012_manual_jobs.sql."""
    company: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=2000, pattern=r"^https?://\S+$")
    location_raw: str = Field("", max_length=200)
    description_text: str = Field(min_length=1, max_length=60000)
    posted_at: datetime | None = None

    @field_validator("company", "title", "description_text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class ContactImport(BaseModel):
    kind: Literal["hr", "founder"]
    source: str = Field(min_length=1, max_length=200)  # where the list came from; kept on every row
    csv: str = Field(min_length=1, max_length=2_000_000)
    dry_run: bool = False  # preview: parse and report, save nothing


class ContactDelete(BaseModel):
    email: str | None = Field(None, max_length=254)  # a removal request
    source: str | None = Field(None, max_length=200)  # a whole upload that shouldn't be there

    @model_validator(mode="after")
    def one_of(self) -> "ContactDelete":
        if bool(self.email) == bool(self.source):
            raise ValueError("give exactly one of email or source")
        return self


CONTACT_COLUMNS = ("kind", *ALIASES)
# One statement per upload (the Worker has 10 ms of CPU per request): rows with an email are
# matched on it, case-insensitive; a later file fills in what it has and keeps what it lacks.
UPSERT_CONTACTS = f"""
INSERT INTO contacts ({", ".join(CONTACT_COLUMNS)}, source)
SELECT u.*, $12 FROM unnest({", ".join(f"${i}::text[]" for i in range(1, 12))}) AS u({", ".join(CONTACT_COLUMNS)})
ON CONFLICT (lower(email)) WHERE email IS NOT NULL DO UPDATE SET
  kind = EXCLUDED.kind, name = EXCLUDED.name, company = EXCLUDED.company, source = EXCLUDED.source,
  {", ".join(f"{c} = COALESCE(EXCLUDED.{c}, contacts.{c})" for c in ALIASES if c not in ("name", "company", "email"))}
RETURNING (xmax = 0) AS inserted
"""
# Rows without an email can't be matched on it: skip a name already listed at the same company.
INSERT_NO_EMAIL = f"""
INSERT INTO contacts ({", ".join(CONTACT_COLUMNS)}, source)
SELECT u.*, $12 FROM unnest({", ".join(f"${i}::text[]" for i in range(1, 12))}) AS u({", ".join(CONTACT_COLUMNS)})
WHERE NOT EXISTS (SELECT 1 FROM contacts c WHERE c.email IS NULL AND c.kind = u.kind
                  AND lower(c.name) = lower(u.name) AND lower(c.company) = lower(u.company))
RETURNING true AS inserted
"""


def _columns_of(rows: list[dict[str, Any]]) -> list[list[Any]]:
    return [[r[c] for r in rows] for c in CONTACT_COLUMNS]


MANUAL_COLUMNS = ("id, company, title, url, location_raw, posted_at, added_at, closed_at, "
                  "CASE WHEN closed_at IS NULL THEN 'open' ELSE 'closed' END AS status")


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

    @r.get("/jobs")
    async def manual_jobs(response: Response, _: str = Depends(require_admin), db: Database = Depends(get_db)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return {"jobs": await db.all(f"SELECT {MANUAL_COLUMNS} FROM manual_jobs ORDER BY id DESC LIMIT 200")}

    @r.post("/jobs", status_code=201)
    async def add_job(job: ManualJob, uid: str = Depends(require_admin), db: Database = Depends(get_db)) -> dict[str, Any]:
        # Listed after the next pipeline run, labelled by the same rules as every job (sources/manual.py).
        async with db.transaction():
            rows = await db.all(
                "INSERT INTO manual_jobs (company, title, url, location_raw, description_text, posted_at, added_by) "
                f"VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING {MANUAL_COLUMNS}",
                [job.company, job.title, job.url, job.location_raw.strip(), job.description_text, job.posted_at, uid])
        return rows[0]

    @r.post("/jobs/{job_id}/close")
    async def close_job(job_id: int, _: str = Depends(require_admin), db: Database = Depends(get_db)) -> dict[str, Any]:
        async with db.transaction():
            rows = await db.all(f"UPDATE manual_jobs SET closed_at = COALESCE(closed_at, now()) WHERE id = $1 "
                                f"RETURNING {MANUAL_COLUMNS}", [job_id])
        if not rows:
            raise HTTPException(status_code=404, detail="no such job")
        return rows[0]

    @r.get("/contacts")
    async def contacts(response: Response, _: str = Depends(require_admin), db: Database = Depends(get_db)) -> dict[str, Any]:
        """What's in the lists, never the people: counts per upload, and reveals this week."""
        response.headers["Cache-Control"] = "no-store"
        lists = await db.all("SELECT kind, source, COUNT(*) AS n, COUNT(email) AS with_email, COUNT(phone) AS with_phone "
                             "FROM contacts GROUP BY 1, 2 ORDER BY 1, 2")
        reveals = await db.all("SELECT COUNT(*) AS n FROM contact_reveals WHERE created_at > now() - interval '7 days'")
        return {"total": sum(int(x["n"]) for x in lists), "reveals_7d": int(reveals[0]["n"]),
                "lists": [{k: (int(v) if k in ("n", "with_email", "with_phone") else v) for k, v in x.items()} for x in lists]}

    @r.post("/contacts/import")
    async def import_contacts(body: ContactImport, response: Response, _: str = Depends(require_admin),
                              db: Database = Depends(get_db)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        rows, errors = parse(body.csv, body.kind)
        # The same email twice in one file: the later row wins (one statement can't update a row twice).
        by_email: dict[str, dict[str, Any]] = {}
        no_email = []
        for row in rows:
            if row["email"]:
                by_email[row["email"]] = row
            else:
                no_email.append(row)
        report = {"valid": len(rows), "errors": errors[:50], "error_count": len(errors), "added": 0, "updated": 0,
                  # The preview shows a few parsed rows, phone numbers masked: it's for checking columns.
                  "sample": [{**row, "phone": "•••" if row["phone"] else None} for row in rows[:5]]}
        if body.dry_run or not rows:
            return report
        source = body.source.strip()
        async with db.transaction():
            done = []
            if by_email:
                done += await db.all(UPSERT_CONTACTS, [*_columns_of(list(by_email.values())), source])
            if no_email:
                done += await db.all(INSERT_NO_EMAIL, [*_columns_of(no_email), source])
        report["added"] = sum(1 for d in done if d["inserted"])
        report["updated"] = len(done) - report["added"]
        return report

    @r.post("/contacts/delete")
    async def delete_contacts(body: ContactDelete, _: str = Depends(require_admin), db: Database = Depends(get_db)) -> dict[str, int]:
        async with db.transaction():
            if body.email:
                gone = await db.all("DELETE FROM contacts WHERE lower(email) = lower($1) RETURNING id", [body.email.strip()])
            else:
                gone = await db.all("DELETE FROM contacts WHERE source = $1 RETURNING id", [body.source.strip()])
        return {"deleted": len(gone)}

    return r
