"""Jobicy (jobicy.com): a remote-jobs board with a free public JSON API.

A board, not an ATS: one entry in config/companies.yaml (slug "remote") returns many companies'
jobs, read by category (config/boards.yaml). No key: Jobicy's paid key only swaps in direct ATS
links, and this project stays on free tiers.

Terms (https://jobicy.com/jobs-rss-feed, "Fair use"), and how they are kept:
- Credit Jobicy and keep Apply on the Jobicy listing: `url` is the Jobicy page, and the site
  labels these jobs "via Jobicy".
- The feed only holds the last 7 days, and a job leaving it may still be open. So a job is never
  closed for being missing: `still_open` asks Jobicy's batch status endpoint about stored jobs the
  feed no longer lists, and scripts/fetch_jobs.py keeps the active ones open.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import yaml

from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "jobicy"
LABEL = "Jobicy"
BOARD = True  # many companies' jobs: shown only for companies not fetched directly
DAILY = True  # a 7-day feed; once a day is plenty, and Jobicy asks for a few passes a day at most
JOBS_URL = "https://jobicy.com/api/jobs"
STATUS_URL = "https://jobicy.com/api/jobs/status"
STATUS_BATCH = 100  # the status endpoint's limit per request
CONFIG = Path(__file__).resolve().parent.parent / "config" / "boards.yaml"


def settings(path: Path = CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())[NAME]


def jobs_url(industry: str, cursor: str | None = None) -> str:
    params = {"count": 100, "industry": industry}
    if cursor:
        params["cursor"] = cursor
    return f"{JOBS_URL}?{urlencode(params)}"


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    """For scripts/verify_companies.py: the first page of the first category."""
    conf = settings()
    payload = http.get_json(jobs_url(conf["industries"][0]))
    return None if payload is None else [j.title for j in parse(payload, Company(LABEL, NAME, slug))]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    conf = settings()
    pages: list[Any] = []
    for industry in conf["industries"]:
        cursor = None
        for _ in range(int(conf.get("max_pages", 10))):
            payload = http.get_json(jobs_url(industry, cursor)) or {}
            pages.append(payload)
            cursor = payload.get("nextCursor")
            if not cursor:
                break
    return parse(pages, company, skip_levels=set(conf.get("skip_levels") or []))


def still_open(http: HttpClient, external_ids: list[str]) -> set[str]:
    """The ids Jobicy reports as active. "closed" and "unknown" are left out, so those jobs follow
    the normal missed-run rule; nothing is closed on absence from the 7-day feed alone."""
    ids = [i for i in external_ids if i.isdigit()]
    active: set[str] = set()
    for start in range(0, len(ids), STATUS_BATCH):
        batch = ids[start:start + STATUS_BATCH]
        payload = http.get_json(f"{STATUS_URL}?{urlencode({'ids': ','.join(batch)})}") or {}
        active |= {str(j["id"]) for j in payload.get("jobs") or [] if j.get("status") == "active"}
    return active


def parse(payload: Any, company: Company, skip_levels: set[str] | None = None) -> list[Job]:
    """One API response, or a list of them. A job listed in two categories is kept once."""
    responses = payload if isinstance(payload, list) else [payload]
    seen: set[str] = set()
    jobs = []
    for response in responses:
        for raw in (response or {}).get("jobs") or []:
            # A structured screen, like india_only: a "Senior" or "Director" listing is never a
            # fresher role, and its text may not say so in years (precision over recall).
            if skip_levels and (raw.get("jobLevel") or "").strip() in skip_levels:
                continue
            job = _job(raw, company)
            if job and job.external_id not in seen:
                seen.add(job.external_id)
                jobs.append(job)
    return jobs


def location(geo: str) -> str:
    """"Ireland,  Portugal,  UK" -> "Remote, Ireland, Portugal, UK". "Anywhere" stays, which the
    location rules read as remote with no restriction; regions (LATAM, EMEA) are read as theirs."""
    places = [p.strip() for p in (geo or "").split(",") if p.strip()]
    return "Remote, " + (", ".join(places) or "Anywhere")


def _job(raw: dict[str, Any], company: Company) -> Job | None:
    title, url, name = (raw.get("jobTitle") or "").strip(), raw.get("url"), (raw.get("companyName") or "").strip()
    if not (raw.get("id") and title and url and name):
        return None
    return Job(
        source=NAME,
        external_id=str(raw["id"]),
        company=name,
        company_slug=company.slug,
        title=title[:200],
        url=url,  # the Jobicy listing, as the terms ask
        location_raw=location(raw.get("jobGeo") or ""),
        description_text=html_to_text(raw.get("jobDescription") or raw.get("jobExcerpt") or ""),
        posted_at=to_utc_iso(raw.get("pubDate")),
        department=", ".join(raw.get("jobIndustry") or []) or None,
        employment_type=", ".join(raw.get("jobType") or []) or None,
        ats_workplace_type="remote",  # every Jobicy job is remote
    )
