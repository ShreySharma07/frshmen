"""Oracle Recruiting Cloud career sites (KPMG India, EXL...): the JSON API the career site itself calls.

Slug: "<host>/<siteNumber>", e.g. "ejgk.fa.em2.oraclecloud.com/CX_1" for
https://ejgk.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1. The list call
(recruitingCEJobRequisitions) gives titles and locations, newest first, 25 a page; one detail
call per job (recruitingCEJobRequisitionDetails) gives the text. These hosts publish no
robots.txt. india_only boards keep jobs whose primary or secondary location is in India.
"""

from __future__ import annotations

from typing import Any

from extract.profile import load_profile
from extract.role import match_role
from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "oracle"
PAGE = 25
MAX_PAGES = 40  # 1,000 jobs per board per run
LIST_PAGES = 4  # the verifier only needs a sample
MAX_DETAILS = 150
DETAIL_FRESH_DAYS = 3
API = "https://{host}/hcmRestApi/resources/latest"


def _parts(slug: str) -> tuple[str, str]:
    host, _, site = slug.partition("/")
    return host, site


def list_url(slug: str, offset: int) -> str:
    host, site = _parts(slug)
    return (f"{API.format(host=host)}/recruitingCEJobRequisitions?onlyData=true"
            f"&expand=requisitionList.secondaryLocations"
            f"&finder=findReqs;siteNumber={site},limit={PAGE},offset={offset},sortBy=POSTING_DATES_DESC")


def detail_url(slug: str, job_id: str) -> str:
    host, site = _parts(slug)
    return (f"{API.format(host=host)}/recruitingCEJobRequisitionDetails?expand=all&onlyData=true"
            f"&finder=ById;Id=%22{job_id}%22,siteNumber={site}")


def job_url(slug: str, job_id: str) -> str:
    host, site = _parts(slug)
    return f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{job_id}"


def requisitions(http: HttpClient, slug: str, max_pages: int = MAX_PAGES) -> list[dict[str, Any]] | None:
    """Every listed requisition, newest first; None if the site doesn't answer like Oracle Recruiting."""
    out: list[dict[str, Any]] = []
    for page in range(max_pages):
        data = http.get_json(list_url(slug, page * PAGE))
        items = (data or {}).get("items") if isinstance(data, dict) else None
        if not items:
            return out if page else None
        search = items[0]
        batch = search.get("requisitionList") or []
        out += batch
        if not batch or len(out) >= (search.get("TotalJobsCount") or 0):
            break
    return out


def _in_india(req: dict[str, Any]) -> bool:
    if req.get("PrimaryLocationCountry") == "IN":
        return True
    return any((loc.get("CountryCode") or loc.get("Country")) == "IN" for loc in req.get("secondaryLocations") or [])


def _title_could_fit(title: str) -> bool:
    # Same screen as careersite: these boards are mostly audit, tax and consulting roles.
    m = match_role(title, "", load_profile())
    return m.is_target or m.family is not None


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    reqs = requisitions(http, slug, LIST_PAGES)
    return None if reqs is None else [(r.get("Title") or "").strip() for r in reqs]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    reqs = requisitions(http, company.slug) or []
    picked = [r for r in reqs if r.get("Id") and _title_could_fit(r.get("Title") or "")
              and (not company.india_only or _in_india(r))]
    jobs = []
    for req in picked[:MAX_DETAILS]:
        detail = http.get_json(detail_url(company.slug, req["Id"]), fresh_days=DETAIL_FRESH_DAYS)
        job = parse_detail(detail, company, req)
        if job:
            jobs.append(job)
    return jobs


def parse_detail(payload: Any, company: Company, listed: dict[str, Any] | None = None) -> Job | None:
    items = (payload or {}).get("items") if isinstance(payload, dict) else None
    info = items[0] if items else None
    if not isinstance(info, dict) or not info.get("Title"):
        return None
    # External fields are what the career site shows; internal copies are often identical.
    parts = []
    for key in ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr"):
        text = html_to_text(info.get(key))
        if text and text not in parts:
            parts.append(text)
    locations = [info.get("PrimaryLocation") or ""] + [
        loc.get("Name") or "" for loc in info.get("secondaryLocations") or []]
    workplace = info.get("WorkplaceType") or (listed or {}).get("WorkplaceType") or None
    return Job(
        source=NAME,
        external_id=str(info.get("Id")),
        company=company.name,
        company_slug=company.slug,
        title=info["Title"].strip(),
        url=job_url(company.slug, str(info.get("Id"))),
        location_raw=" / ".join(loc.strip() for loc in locations if loc and loc.strip()),
        description_text="\n\n".join(parts),
        posted_at=to_utc_iso(info.get("ExternalPostedStartDate")),
        employment_type=info.get("JobSchedule"),
        ats_workplace_type=workplace,
    )
