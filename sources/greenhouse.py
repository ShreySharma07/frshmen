"""Greenhouse job board API: one call returns every open job with its description."""

from __future__ import annotations

from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "greenhouse"


def url_for(slug: str) -> str:
    return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(http.get_json(url_for(company.slug)), company)


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, dict):
        return []
    jobs = []
    for raw in payload.get("jobs", []):
        departments = [d.get("name") for d in raw.get("departments") or [] if d.get("name")]
        jobs.append(Job(
            source=NAME,
            external_id=str(raw["id"]),
            company=company.name,
            company_slug=company.slug,
            title=(raw.get("title") or "").strip(),
            url=raw.get("absolute_url") or "",
            location_raw=((raw.get("location") or {}).get("name") or "").strip(),
            description_text=html_to_text(raw.get("content")),
            # first_published is when the role went live; updated_at moves on every edit.
            posted_at=to_utc_iso(raw.get("first_published") or raw.get("updated_at")),
            department=", ".join(departments) or None,
        ))
    return jobs
