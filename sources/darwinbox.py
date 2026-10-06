"""Darwinbox careers sites (common with Indian companies): a paged JSON list plus one JSON call per job.

Slug: the subdomain on darwinbox.in ("zepto"), or a full host when the site lives
elsewhere ("straive.darwinbox.com"). These are the endpoints the careers page
itself calls; the site publishes no robots.txt.
"""

from __future__ import annotations

from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import could_be_target, experience_line
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "darwinbox"
PAGE_SIZE = 50
MAX_PAGES = 20
MAX_DETAILS = 150


def host(slug: str) -> str:
    return slug if "." in slug else f"{slug}.darwinbox.in"


def list_url(slug: str, page: int) -> str:
    return f"https://{host(slug)}/ms/candidateapi/job?page={page}&limit={PAGE_SIZE}"


def detail_url(slug: str, job_id: str) -> str:
    return f"https://{host(slug)}/ms/candidateapi/job/{job_id}"


def job_url(slug: str, job_id: str) -> str:
    return f"https://{host(slug)}/ms/candidatev2/main/careers/jobDetails/{job_id}"


def _list_payload(payload: Any) -> tuple[list[dict[str, Any]], int] | None:
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return None
    msg = payload.get("message") or {}
    if not isinstance(msg, dict):
        return None
    return list(msg.get("jobs") or []), int(msg.get("jobscount") or 0)


def list_jobs(http: HttpClient, slug: str) -> list[dict[str, Any]] | None:
    first = _list_payload(http.get_json(list_url(slug, 1)))
    if first is None:
        return None
    jobs, total = first
    page = 1
    while len(jobs) < total and page < MAX_PAGES:
        page += 1
        more = _list_payload(http.get_json(list_url(slug, page)))
        if not more or not more[0]:
            break
        jobs += more[0]
    return jobs


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    jobs = list_jobs(http, slug)
    return None if jobs is None else [(j.get("title") or "").strip() for j in jobs]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    listed = [j for j in list_jobs(http, company.slug) or [] if could_be_target(j.get("title") or "")]
    jobs = []
    for item in listed[:MAX_DETAILS]:
        detail = http.get_json(detail_url(company.slug, item["id"]))
        rows = ((detail or {}).get("message") or {}).get("job") if isinstance(detail, dict) else None
        jobs.append(parse(item, rows[0] if rows else {}, company))
    return jobs


def parse(item: dict[str, Any], detail: dict[str, Any], company: Company) -> Job:
    """`item` is the list entry, `detail` the per-job entry (empty if that call failed)."""
    raw = {**item, **detail}
    locations = raw.get("officelocation_show_arr_list") or raw.get("tool_tip_locations") or [raw.get("officelocation_show_arr") or ""]
    location_raw = " / ".join(dict.fromkeys(" ".join(loc.replace("\r", "").split()) for loc in locations if loc and loc.strip()))
    # The list gives years ("2", "5"); the detail gives "2 - 5 Years" (and months in its *_num fields).
    experience = detail.get("experience") or (
        f"{item['experience_from_num']} - {item['experience_to_num']} Years"
        if item.get("experience_from_num") not in (None, "") and item.get("experience_to_num") not in (None, "") else "")
    body = html_to_text(detail.get("jd"))
    posted = raw.get("posted_on") or raw.get("job_posting_on")
    return Job(
        source=NAME,
        external_id=str(raw["id"]),
        company=company.name,
        company_slug=company.slug,
        title=(raw.get("title") or raw.get("designation_name") or "").strip(),
        url=job_url(company.slug, raw["id"]),
        location_raw=location_raw,
        description_text="\n\n".join(p for p in [experience_line(experience), body] if p),
        posted_at=to_utc_iso(int(posted) * 1000) if str(posted or "").isdigit() else to_utc_iso(raw.get("created_on")),
        department=raw.get("department") or None,
        employment_type=raw.get("emp_type") or None,
        ats_workplace_type="remote" if detail.get("is_remote") in (1, "1", True) else None,
    )
