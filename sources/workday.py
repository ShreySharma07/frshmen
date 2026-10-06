"""Workday careers sites: the public sitemap lists every job, one JSON call per job gives its text.

Slug format: "<tenant>/<wdN>/<site>", e.g. "browserstack/wd3/External" for
https://browserstack.wd3.myworkdayjobs.com/External. The sitemap and the per-job
JSON are plain GETs the careers site itself serves; robots.txt doesn't exclude them.
"""

from __future__ import annotations

import re
from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import could_be_target
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "workday"
# Per-run cap on detail requests per board; the title screen keeps real boards well under it.
MAX_DETAILS = 150


def _parts(slug: str) -> tuple[str, str, str]:
    tenant, wd, site = slug.split("/")
    return tenant, wd, site


def sitemap_url(slug: str) -> str:
    tenant, wd, site = _parts(slug)
    return f"https://{tenant}.{wd}.myworkdayjobs.com/{site}/siteMap.xml"


def detail_url(slug: str, path: str) -> str:
    tenant, wd, site = _parts(slug)
    return f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{path}"


def job_paths(sitemap: str, site: str) -> list[str]:
    """"/job/<location>/<Title>_<ReqId>" paths, in sitemap order."""
    paths = re.findall(rf"<loc>https://[^<]*?/{re.escape(site)}(/job/[^<]+)</loc>", sitemap)
    return list(dict.fromkeys(paths))


def title_from_path(path: str) -> str:
    """"/job/India-Remote/ML-Engineer_JR103661" -> "ML Engineer" (good enough for the title screen)."""
    last = path.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"_[A-Za-z]*\d[\w-]*$", "", last).replace("-", " ").strip()


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    sitemap = http.get_text(sitemap_url(slug))
    if sitemap is None or "<urlset" not in sitemap:
        return None
    return [title_from_path(p) for p in job_paths(sitemap, _parts(slug)[2])]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    sitemap = http.get_text(sitemap_url(company.slug)) or ""
    paths = [p for p in job_paths(sitemap, _parts(company.slug)[2]) if could_be_target(title_from_path(p))]
    jobs = []
    for path in paths[:MAX_DETAILS]:
        job = parse_detail(http.get_json(detail_url(company.slug, path)), company)
        if job:
            jobs.append(job)
    return jobs


def parse_detail(payload: Any, company: Company) -> Job | None:
    info = (payload or {}).get("jobPostingInfo") if isinstance(payload, dict) else None
    if not isinstance(info, dict) or not info.get("title"):
        return None
    locations = [info.get("location") or ""] + list(info.get("additionalLocations") or [])
    country = (info.get("country") or {}).get("descriptor")
    return Job(
        source=NAME,
        external_id=str(info.get("jobReqId") or info.get("jobPostingId") or info["id"]),
        company=company.name,
        company_slug=company.slug,
        title=info["title"].strip(),
        url=info.get("externalUrl") or "",
        location_raw=" / ".join(loc.strip() for loc in locations if loc and loc.strip()),
        description_text=html_to_text(info.get("jobDescription")),
        # startDate is the posting date; postedOn is only "Posted 30+ Days Ago".
        posted_at=to_utc_iso(info.get("startDate")),
        employment_type=info.get("timeType"),
        ats_countries=[country] if country else [],
    )
