"""Himalayas (himalayas.app): a remote-jobs board with a free public JSON API.

A board, not an ATS: one board entry in config/companies.yaml (slug "remote") returns many
companies' jobs. Searched with the queries in config/boards.yaml, Entry- and Mid-level only.
Without a key the API allows fewer requests; HIMALAYAS_API_KEY (a free key, sent as a Bearer
token) raises that to 60 a minute and 10,000 a day.

Terms (https://himalayas.app/terms#api), and how they are kept:
- Apply uses `applicationLink` unchanged: it becomes `Job.url`, which the Apply button opens.
- A visible link back to Himalayas: `applicationLink` is the job's page on himalayas.app, and the
  site labels these jobs "via Himalayas".
- Expired jobs are removed: a job missing from a day's results is closed by publish_pg.py.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import yaml

from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "himalayas"
LABEL = "Himalayas"
BOARD = True  # many companies' jobs: shown only for companies not fetched directly
DAILY = True  # the data refreshes daily; read only in the daily run
SEARCH_URL = "https://himalayas.app/jobs/api/search"
CONFIG = Path(__file__).resolve().parent.parent / "config" / "boards.yaml"
# Above this many countries, location_raw names a count, not the list (the list is in ats_countries).
_MAX_NAMED_COUNTRIES = 3


def settings(path: Path = CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())[NAME]


def search_url(query: str, seniority: list[str], page: int) -> str:
    return f"{SEARCH_URL}?" + urlencode({"q": query, "seniority": ",".join(seniority), "sort": "recent",
                                         "page": page})


def auth_headers() -> dict[str, str] | None:
    key = os.environ.get("HIMALAYAS_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else None


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    """For scripts/verify_companies.py: one page of the first query, enough to show the API answers."""
    conf = settings()
    payload = http.get_json(search_url(conf["queries"][0], conf["seniority"], 1), headers=auth_headers())
    return None if payload is None else [j.title for j in parse(payload, Company(LABEL, NAME, slug))]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    conf = settings()
    headers = auth_headers()
    pages: list[Any] = []
    for query in conf["queries"]:
        for page in range(1, int(conf.get("max_pages", 10)) + 1):
            payload = http.get_json(search_url(query, conf["seniority"], page), headers=headers)
            pages.append(payload)
            # Every page but the last holds 20; totalCount is only an estimate, so don't trust it.
            if not (payload or {}).get("jobs") or len(payload["jobs"]) < 20:
                break
    return parse(pages, company)


def parse(payload: Any, company: Company) -> list[Job]:
    """One search response, or a list of them. A job found by several queries is kept once."""
    responses = payload if isinstance(payload, list) else [payload]
    seen: set[str] = set()
    jobs = []
    for response in responses:
        for raw in (response or {}).get("jobs") or []:
            job = _job(raw, company)
            if job and job.external_id not in seen:
                seen.add(job.external_id)
                jobs.append(job)
    return jobs


def external_id(guid: str) -> str:
    """"https://himalayas.app/companies/acme/jobs/ml-engineer" -> "acme/jobs/ml-engineer"."""
    path = urlparse(guid).path.strip("/")
    return path.removeprefix("companies/") or guid


def location(countries: list[str]) -> str:
    if not countries:
        return "Remote, Worldwide"
    if len(countries) <= _MAX_NAMED_COUNTRIES:
        return "Remote, " + ", ".join(countries)
    return f"Remote, {len(countries)} countries"


def _job(raw: dict[str, Any], company: Company) -> Job | None:
    guid, title, url = raw.get("guid"), (raw.get("title") or "").strip(), raw.get("applicationLink")
    if not (guid and title and url and raw.get("companyName")):
        return None
    countries = [c for c in raw.get("locationRestrictions") or [] if isinstance(c, str)]
    return Job(
        source=NAME,
        external_id=external_id(guid),
        company=raw["companyName"].strip(),
        company_slug=company.slug,
        title=title[:200],
        url=url,  # unchanged, as the terms ask
        location_raw=location(countries),
        description_text=html_to_text(raw.get("description") or raw.get("excerpt") or ""),
        # pubDate is when the job was last updated; the nearest the API has to a posting date.
        # Unix seconds here; to_utc_iso takes milliseconds.
        posted_at=to_utc_iso(raw["pubDate"] * 1000) if isinstance(raw.get("pubDate"), (int, float)) else None,
        department=", ".join(raw.get("parentCategories") or []) or None,
        employment_type=raw.get("employmentType"),
        ats_workplace_type="remote",  # every Himalayas job is remote
        ats_countries=countries,
    )
