"""Gem job boards (jobs.gem.com/<slug>): Gem's public Job Board API, one call for every job.

https://api.gem.com/job_board/v0/<slug>/job_posts/ needs no key (documented at
api.gem.com/job_board/v0/reference) and carries each job's full text.
"""

from __future__ import annotations

from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "gem"

_WORKPLACE = {"remote": "remote", "hybrid": "hybrid", "in_office": "onsite", "onsite": "onsite"}


def url_for(slug: str) -> str:
    return f"https://api.gem.com/job_board/v0/{slug}/job_posts/"


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    data = http.get_json(url_for(slug))
    return None if not isinstance(data, list) else [(j.get("title") or "").strip() for j in data]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(http.get_json(url_for(company.slug)), company)


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, list):
        return []
    jobs = []
    for raw in payload:
        offices = [((o.get("location") or {}).get("name") or o.get("name") or "") for o in raw.get("offices") or []
                   if not o.get("deleted_at")]
        location = " / ".join(dict.fromkeys(p for p in [(raw.get("location") or {}).get("name") or ""] + offices if p))
        departments = [d.get("name") for d in raw.get("departments") or [] if d.get("name")]
        jobs.append(Job(
            source=NAME,
            external_id=str(raw["id"]),
            company=company.name,
            company_slug=company.slug,
            title=(raw.get("title") or "").strip(),
            url=raw.get("absolute_url") or "",
            location_raw=location,
            # content_plain keeps Gem's line breaks; the HTML one can come back run together.
            description_text=(raw.get("content_plain") or "").strip() or html_to_text(raw.get("content")),
            posted_at=to_utc_iso(raw.get("first_published_at") or raw.get("created_at")),
            department=departments[0] if departments else None,
            employment_type=raw.get("employment_type"),
            ats_workplace_type=_WORKPLACE.get(raw.get("location_type") or ""),
        ))
    return jobs
