"""Workable job widget API: one call returns every published job, with its description.

https://apply.workable.com/api/v1/widget/accounts/<slug>?details=true. A job open in several
countries is listed once per country under the same shortcode; those are merged into one job.
The host throttles hard, so sources/http.py spaces requests to it 5 s apart.
"""

from __future__ import annotations

from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "workable"


def url_for(slug: str) -> str:
    return f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    data = http.get_json(url_for(slug))
    return None if not isinstance(data, dict) else [(j.get("title") or "").strip() for j in data.get("jobs") or []]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(http.get_json(url_for(company.slug)), company)


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, dict):
        return []
    by_code: dict[str, Job] = {}
    for raw in payload.get("jobs") or []:
        code = raw.get("shortcode")
        if not code or not raw.get("title"):
            continue
        places = [_place(loc) for loc in raw.get("locations") or [] if not loc.get("hidden")] or [_place(raw)]
        countries = [loc["countryCode"] for loc in raw.get("locations") or [] if loc.get("countryCode")]
        if code in by_code:  # same job, another country
            job = by_code[code]
            job.location_raw = " / ".join(dict.fromkeys(job.location_raw.split(" / ") + places))
            job.ats_countries = list(dict.fromkeys(job.ats_countries + countries))
            continue
        by_code[code] = Job(
            source=NAME,
            external_id=code,
            company=company.name,
            company_slug=company.slug,
            title=raw["title"].strip(),
            url=raw.get("url") or raw.get("shortlink") or f"https://apply.workable.com/j/{code}",
            location_raw=" / ".join(p for p in dict.fromkeys(places) if p),
            description_text=html_to_text(raw.get("description")) or "",
            posted_at=to_utc_iso(raw.get("published_on") or raw.get("created_at")),
            department=raw.get("department") or raw.get("function") or None,
            employment_type=raw.get("employment_type") or None,
            ats_workplace_type="remote" if raw.get("telecommuting") else None,
            ats_countries=list(dict.fromkeys(countries)),
        )
    return list(by_code.values())


def _place(loc: dict[str, Any]) -> str:
    return ", ".join(p.strip() for p in (loc.get("city"), loc.get("region") or loc.get("state"), loc.get("country"))
                     if p and p.strip())
