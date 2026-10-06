"""Ashby posting API: one call returns every listed job with its description."""

from __future__ import annotations

from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "ashby"

_WORKPLACE = {"OnSite": "onsite", "Hybrid": "hybrid", "Remote": "remote"}


def url_for(slug: str) -> str:
    return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(http.get_json(url_for(company.slug)), company)


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, dict):
        return []
    jobs = []
    for raw in payload.get("jobs", []):
        if raw.get("isListed") is False:
            continue
        locations = [raw.get("location") or ""] + [
            s.get("location") or "" for s in raw.get("secondaryLocations") or []
        ]
        country = ((raw.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
        jobs.append(Job(
            source=NAME,
            external_id=str(raw["id"]),
            company=company.name,
            company_slug=company.slug,
            title=(raw.get("title") or "").strip(),
            url=raw.get("jobUrl") or "",
            location_raw=" / ".join(loc.strip() for loc in locations if loc.strip()),
            # descriptionPlain keeps Ashby's own line breaks; the HTML one is often run together.
            description_text=(raw.get("descriptionPlain") or "").strip() or html_to_text(raw.get("descriptionHtml")),
            posted_at=to_utc_iso(raw.get("publishedAt")),
            department=raw.get("department") or raw.get("team"),
            employment_type=raw.get("employmentType"),
            ats_workplace_type=_WORKPLACE.get(raw.get("workplaceType") or "") or ("remote" if raw.get("isRemote") else None),
            ats_countries=[country] if country else [],
        ))
    return jobs
