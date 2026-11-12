"""Jobs YC startups post on their Y Combinator company page (ycombinator.com/companies/<slug>/jobs).

Many YC companies list their openings only there. The page is public (robots.txt allows
/companies/<slug>/jobs; only the /companies?<filters> directory search is disallowed), it links
each job, and every job page carries schema.org JobPosting data, read by sources/careersite.py's
page parser. Never the login-walled Work at a Startup application pages.
"""

from __future__ import annotations

import re
from html import unescape

from sources import careersite
from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import could_be_target

NAME = "yc_jobs"
MAX_DETAILS = 40  # a YC company page rarely lists more than a dozen jobs
DETAIL_FRESH_DAYS = 3
BASE = "https://www.ycombinator.com/companies"


def list_url(slug: str) -> str:
    return f"{BASE}/{slug}/jobs"


def job_links(html: str, slug: str) -> list[tuple[str, str]]:
    """(job URL, title words) for each job the company page links, in page order.

    "/companies/brickanta/jobs/dM8327V-forward-deployed-engineer" -> "forward deployed engineer".
    Only this company's jobs: the page also links other YC pages.
    """
    pattern = re.compile(rf"(?:https://www\.ycombinator\.com)?/companies/{re.escape(slug)}/jobs/([A-Za-z0-9]+)-([a-z0-9-]+)")
    out: dict[str, str] = {}
    for m in pattern.finditer(unescape(html or "")):
        out.setdefault(f"{BASE}/{slug}/jobs/{m[1]}-{m[2]}", m[2].replace("-", " "))
    return list(out.items())


def _links(http: HttpClient, slug: str) -> list[tuple[str, str]] | None:
    html = http.get_text(list_url(slug))
    return None if html is None else job_links(html, slug)


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    links = _links(http, slug)
    return None if links is None else [words for _, words in links]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    jobs = []
    for url, words in [(u, w) for u, w in _links(http, company.slug) or [] if could_be_target(w)][:MAX_DETAILS]:
        job = parse_page(http.get_text(url, fresh_days=DETAIL_FRESH_DAYS) or "", url, company)
        if job:
            jobs.append(job)
    return jobs


def parse_page(html: str, url: str, company: Company) -> Job | None:
    job = careersite.parse_page(html, url, company)
    if job is None:
        return None
    job.source = NAME
    # The short code before the title words ("dM8327V") is YC's stable id for the job.
    m = re.search(r"/jobs/([A-Za-z0-9]+)-", url)
    job.external_id = m.group(1) if m else job.external_id
    return job
