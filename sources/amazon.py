"""amazon.jobs: the public search JSON the site itself uses (robots.txt only disallows /internal).

Slug: "IND" (a normalized country code). Only India is fetched, as for every MNC board;
each page of 100 carries full descriptions and qualifications, so there are no per-job calls.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import could_be_target
from sources.text import html_to_text

NAME = "amazon"
PAGE_SIZE = 100
MAX_PAGES = 40


def page_url(country: str, offset: int) -> str:
    return (f"https://www.amazon.jobs/en/search.json?normalized_country_code%5B%5D={country}"
            f"&result_limit={PAGE_SIZE}&offset={offset}&sort=recent")


def _pages(http: HttpClient, country: str) -> list[dict[str, Any]] | None:
    first = http.get_json(page_url(country, 0))
    if not isinstance(first, dict) or "jobs" not in first:
        return None
    jobs, total = list(first["jobs"]), int(first.get("hits") or 0)
    page = 1
    while len(jobs) < total and page < MAX_PAGES:
        more = http.get_json(page_url(country, page * PAGE_SIZE))
        if not isinstance(more, dict) or not more.get("jobs"):
            break
        jobs += more["jobs"]
        page += 1
    return jobs


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    jobs = _pages(http, slug)
    return None if jobs is None else [(j.get("title") or "").strip() for j in jobs]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    # Amazon India lists thousands of roles; only titles that could be targets become rows.
    return parse([j for j in _pages(http, company.slug) or [] if could_be_target(j.get("title") or "")], company)


def _text(value: Any) -> str:
    # Fields arrive HTML-escaped ("&lt;br/&gt;"), so unescape before stripping tags.
    return html_to_text(html.unescape(value or ""))


def _date(value: str | None) -> str | None:
    try:
        return datetime.strptime((value or "").strip(), "%B %d, %Y").replace(tzinfo=timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
    except ValueError:
        return None


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, list):
        return []
    jobs = []
    for raw in payload:
        sections = [_text(raw.get("description"))]
        for key, heading in (("basic_qualifications", "Basic qualifications"),
                             ("preferred_qualifications", "Preferred qualifications")):
            body = _text(raw.get(key))
            if body:
                sections.append(f"{heading}\n{body}")
        jobs.append(Job(
            source=NAME,
            external_id=str(raw.get("id_icims") or raw["id"]),
            company=company.name,
            company_slug=company.slug,
            title=(raw.get("title") or "").strip(),
            url="https://www.amazon.jobs" + (raw.get("job_path") or ""),
            location_raw=(raw.get("normalized_location") or raw.get("location") or "").strip(),
            description_text="\n\n".join(s for s in sections if s),
            posted_at=_date(raw.get("posted_date")),
            department=raw.get("job_category") or None,
            employment_type=raw.get("job_schedule_type") or None,
            ats_countries=[raw["country_code"]] if raw.get("country_code") else [],
        ))
    return jobs
