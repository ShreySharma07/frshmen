"""Keka careers sites (common with Indian startups): one JSON call returns every active job with its text.

Slug: "<subdomain>" or "<subdomain>/<portal guid>". Without the guid, it is read
from the careers page (`/careers/` is allowed by Keka's robots.txt; the rest of
the host is not). Keka's structured `experience` field ("3-5") is kept as a
sentence in the description so the YoE extractor uses it as evidence.
"""

from __future__ import annotations

import re
from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import experience_line
from sources.timeutil import to_utc_iso

NAME = "keka"
_GUID = re.compile(r"embedjobs/js/([0-9a-f-]{36})|identifier[\"']?\s*[:=]\s*[\"']([0-9a-f-]{36})", re.I)


def _parts(slug: str) -> tuple[str, str | None]:
    sub, _, guid = slug.partition("/")
    return sub, guid or None


def portal_guid(http: HttpClient, sub: str) -> str | None:
    page = http.get_text(f"https://{sub}.keka.com/careers/")
    m = _GUID.search(page or "")
    return (m.group(1) or m.group(2)) if m else None


def list_url(sub: str, guid: str) -> str:
    return f"https://{sub}.keka.com/careers/api/embedjobs/default/active/{guid}"


def _payload(http: HttpClient, slug: str) -> list[dict[str, Any]] | None:
    sub, guid = _parts(slug)
    guid = guid or portal_guid(http, sub)
    if not guid:
        return None
    data = http.get_json(list_url(sub, guid))
    return data if isinstance(data, list) else None


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    data = _payload(http, slug)
    return None if data is None else [(j.get("title") or "").strip() for j in data]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(_payload(http, company.slug) or [], company)


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, list):
        return []
    sub, _ = _parts(company.slug)
    jobs = []
    for raw in payload:
        locations = raw.get("jobLocations") or []
        names = [", ".join(p for p in (loc.get("city") or loc.get("name"), loc.get("countryName")) if p) for loc in locations]
        description = (raw.get("description") or "").strip()
        jobs.append(Job(
            source=NAME,
            external_id=str(raw["id"]),
            company=company.name,
            company_slug=company.slug,
            title=(raw.get("title") or "").strip(),
            url=f"https://{sub}.keka.com/careers/jobdetails/{raw['id']}",
            location_raw=" / ".join(dict.fromkeys(n for n in names if n)),
            description_text="\n\n".join(p for p in [experience_line(raw.get("experience")), description] if p),
            posted_at=to_utc_iso(raw.get("publishedOn")),
            department=raw.get("departmentName") or None,
            ats_countries=list(dict.fromkeys(loc["countryCode"] for loc in locations if loc.get("countryCode"))),
        ))
    return jobs
