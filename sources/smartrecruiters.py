"""SmartRecruiters posting API: a list call for titles and locations, one detail call per job for the text.

https://api.smartrecruiters.com/v1/companies/<slug>/postings pages 100 at a time, newest first;
.../postings/<id> gives the job ad in sections. Boards like Swiggy's are mostly operations and
sales roles, so only titles that could be a target role get a detail call (as for Oracle), and
india_only boards (ServiceNow, Bosch) keep India and remote jobs before any detail is fetched.
"""

from __future__ import annotations

from typing import Any

from extract.profile import load_profile
from extract.role import match_role
from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "smartrecruiters"
API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE = 100
MAX_PAGES = 10  # 1,000 jobs per board per run
MAX_DETAILS = 100
DETAIL_FRESH_DAYS = 3
# The company description says nothing about this job; the other sections hold the requirements.
SECTIONS = ("jobDescription", "qualifications", "additionalInformation")


def list_url(slug: str, offset: int) -> str:
    return f"{API.format(slug=slug)}?limit={PAGE}&offset={offset}"


def detail_url(slug: str, posting_id: str) -> str:
    return f"{API.format(slug=slug)}/{posting_id}"


def postings(http: HttpClient, slug: str, max_pages: int = MAX_PAGES) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(max_pages):
        data = http.get_json(list_url(slug, page * PAGE))
        batch = (data or {}).get("content") if isinstance(data, dict) else None
        if not batch:
            break
        out += batch
        if len(out) >= (data.get("totalFound") or 0):
            break
    return out


def _in_india_or_remote(posting: dict[str, Any]) -> bool:
    loc = posting.get("location") or {}
    return (loc.get("country") or "").lower() == "in" or bool(loc.get("remote"))


def _title_could_fit(title: str) -> bool:
    m = match_role(title, "", load_profile())
    return m.is_target or m.family is not None


def list_titles(http: HttpClient, slug: str) -> list[str]:
    return [(p.get("name") or "").strip() for p in postings(http, slug, 1)]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    picked = [p for p in postings(http, company.slug) if p.get("id") and _title_could_fit(p.get("name") or "")
              and (not company.india_only or _in_india_or_remote(p))]
    jobs = []
    for posting in picked[:MAX_DETAILS]:
        detail = http.get_json(detail_url(company.slug, posting["id"]), fresh_days=DETAIL_FRESH_DAYS)
        job = parse_detail(detail, company)
        if job:
            jobs.append(job)
    return jobs


def parse_detail(payload: Any, company: Company) -> Job | None:
    if not isinstance(payload, dict) or not payload.get("id") or not payload.get("name"):
        return None
    sections = ((payload.get("jobAd") or {}).get("sections")) or {}
    parts = []
    for key in SECTIONS:
        section = sections.get(key) or {}
        body = html_to_text(section.get("text"))
        if body:
            heading = (section.get("title") or "").strip()
            parts.append(f"{heading}\n{body}" if heading else body)
    loc = payload.get("location") or {}
    workplace = "remote" if loc.get("remote") else "hybrid" if loc.get("hybrid") else None
    return Job(
        source=NAME,
        external_id=str(payload["id"]),
        company=company.name,
        company_slug=company.slug,
        title=payload["name"].strip(),
        url=payload.get("postingUrl") or f"https://jobs.smartrecruiters.com/{company.slug}/{payload['id']}",
        location_raw=loc.get("fullLocation") or ", ".join(
            p for p in (loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()) if p),
        description_text="\n\n".join(parts),
        posted_at=to_utc_iso(payload.get("releasedDate")),
        department=((payload.get("function") or {}).get("label")) or None,
        employment_type=((payload.get("typeOfEmployment") or {}).get("label")) or None,
        ats_workplace_type=workplace,
        ats_countries=[loc["country"].upper()] if loc.get("country") else [],
    )
