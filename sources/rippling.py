"""Rippling job boards (ats.rippling.com/<slug>): the board's public JSON, list then one call per job.

The list (api.rippling.com/platform/api/ats/v1/board/<slug>/jobs) has titles and places only, so
descriptions come from /jobs/<uuid>. Like Workday, only titles that could be a target role get
that second call: a 700-job board is mostly sales, and fetching each would hammer the host.
"""

from __future__ import annotations

from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import could_be_target
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "rippling"
MAX_DETAILS = 150
DETAIL_FRESH_DAYS = 3  # job text rarely changes; later runs fetch only new jobs

_API = "https://api.rippling.com/platform/api/ats/v1/board"


def list_url(slug: str) -> str:
    return f"{_API}/{slug}/jobs"


def detail_url(slug: str, uuid: str) -> str:
    return f"{_API}/{slug}/jobs/{uuid}"


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    data = http.get_json(list_url(slug))
    return None if not isinstance(data, list) else [(j.get("name") or "").strip() for j in data]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    listed = http.get_json(list_url(company.slug))
    if not isinstance(listed, list):
        return []
    jobs = []
    for item in [j for j in listed if j.get("uuid") and could_be_target(j.get("name") or "")][:MAX_DETAILS]:
        job = parse_detail(http.get_json(detail_url(company.slug, item["uuid"]), fresh_days=DETAIL_FRESH_DAYS),
                           company, item)
        if job:
            jobs.append(job)
    return jobs


def parse_detail(raw: Any, company: Company, listed: dict[str, Any] | None = None) -> Job | None:
    if not isinstance(raw, dict) or not raw.get("uuid"):
        return None
    listed = listed or {}
    description = raw.get("description") or {}
    # The posting's own text is "role"; "company" is the same About-us block on every job, kept last.
    parts = [description.get("role"), description.get("company")] if isinstance(description, dict) else [description]
    text = "\n\n".join(t for t in (html_to_text(p) for p in parts if p) if t)
    places = raw.get("workLocations") or [((listed.get("workLocation") or {}).get("label") or "")]
    department = raw.get("department") or listed.get("department") or {}
    employment = raw.get("employmentType") or {}
    title = (raw.get("name") or listed.get("name") or "").strip()
    if not title or not text:
        return None
    return Job(
        source=NAME,
        external_id=str(raw["uuid"]),
        company=company.name,
        company_slug=company.slug,
        title=title,
        url=raw.get("url") or listed.get("url") or "",
        location_raw=" / ".join(p.strip() for p in places if p and p.strip()),
        description_text=text,
        posted_at=to_utc_iso(raw.get("createdOn")),
        department=department.get("base_department") or department.get("name") or department.get("label"),
        # {"label": "SALARIED_FT", "id": "Salaried, full-time"}: the id is the readable one.
        employment_type=employment.get("id") if isinstance(employment, dict) else None,
    )
