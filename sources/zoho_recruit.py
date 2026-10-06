"""Zoho Recruit careers sites: the careers page embeds every open job as JSON.

Slug: the careers host, e.g. "wadhwaniai.zohorecruit.in" or a custom domain like
"career.qure.ai". The page carries the jobs in `<input id="jobs" value="[...]">`
before any JavaScript runs; Zoho's robots.txt allows `/jobs/*`.
Field names follow Zoho Recruit's Job Opening module (Posting_Title, City, ...).
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import experience_line
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "zoho_recruit"
_JOBS_INPUT = re.compile(r"<input[^>]*\bid=[\"']jobs[\"'][^>]*>", re.I)
_VALUE = re.compile(r"\bvalue=(\"([^\"]*)\"|'([^']*)')", re.I)


def page_url(slug: str) -> str:
    return f"https://{slug}/jobs/Careers"


def embedded_jobs(page: str | None) -> list[dict[str, Any]] | None:
    tag = _JOBS_INPUT.search(page or "")
    value = _VALUE.search(tag.group(0)) if tag else None
    if not value:
        return None
    try:
        data = json.loads(html.unescape(value.group(2) if value.group(2) is not None else value.group(3)))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    jobs = embedded_jobs(http.get_text(page_url(slug)))
    return None if jobs is None else [_title(j) for j in jobs]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(embedded_jobs(http.get_text(page_url(company.slug))) or [], company)


def _title(raw: dict[str, Any]) -> str:
    return (raw.get("Posting_Title") or raw.get("Job_Opening_Name") or "").strip()


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, list):
        return []
    jobs = []
    for raw in payload:
        if raw.get("Publish") is False:
            continue
        title = _title(raw)
        place = ", ".join(str(raw[k]) for k in ("City", "State", "Country") if raw.get(k))
        remote = raw.get("Remote_Job") in (True, "true", "Yes")
        slugified = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")
        experience = raw.get("Work_Experience") or raw.get("Experience")
        jobs.append(Job(
            source=NAME,
            external_id=str(raw["id"]),
            company=company.name,
            company_slug=company.slug,
            title=title,
            url=f"https://{company.slug}/jobs/Careers/{raw['id']}/{slugified}",
            location_raw=place + (" (Remote)" if remote and place else "Remote" if remote else ""),
            description_text="\n\n".join(p for p in [experience_line(experience), html_to_text(raw.get("Job_Description"))] if p),
            posted_at=to_utc_iso(raw.get("Date_Opened")),
            department=raw.get("Industry") or None,
            employment_type=raw.get("Job_Type") or None,
            ats_workplace_type="remote" if remote else None,
        ))
    return jobs
