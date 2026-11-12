"""Avature career sites (IBM's careers.ibm.com): the public job search pages, then each job page.

Slug: the portal's host and path, e.g. "careers.ibm.com/en_US/careers". The search page
(<portal>/SearchJobs) is plain HTML, paged with jobOffset, and lists each job as a card: a
title link to <portal>/JobDetail?jobId=<id> and a line with level and place. Each job page
carries schema.org JobPosting data, read by sources/careersite.py's page parser. robots.txt
allows these pages (only URLs with "qtvc=" are disallowed, and none are requested).
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, urlparse

from extract.location import extract_location
from sources import careersite
from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import could_be_target

NAME = "avature"
PER_PAGE = 48  # the largest page size the portal offers
MAX_PAGES = 40
LIST_PAGES = 3  # the verifier only needs a sample
MAX_DETAILS = 150
DETAIL_FRESH_DAYS = 3

_CARD = re.compile(r"<article\b.*?</article>", re.S | re.I)
_TITLE = re.compile(r"<h3\b[^>]*>.*?<a\b[^>]*href=\"([^\"]*JobDetail\?[^\"]*jobId=(\d+)[^\"]*)\"[^>]*>(.*?)</a>",
                    re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")


def search_url(slug: str, offset: int) -> str:
    return f"https://{slug}/SearchJobs?listFilterMode=1&jobRecordsPerPage={PER_PAGE}&jobOffset={offset}"


def _text(markup: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAGS.sub(" ", markup))).strip()


def cards(html: str) -> list[dict[str, str]]:
    """{"id", "url", "title", "text"} for each job card on a search page, in page order."""
    out: dict[str, dict[str, str]] = {}
    for card in _CARD.findall(html or ""):
        m = _TITLE.search(card)
        if m and m.group(2) not in out:
            url = unescape(m.group(1))
            out[m.group(2)] = {"id": m.group(2), "url": url, "title": _text(m.group(3)), "text": _text(card)}
    return list(out.values())


def listed(http: HttpClient, slug: str, max_pages: int = MAX_PAGES) -> list[dict[str, str]] | None:
    """Every job card, page by page. None when the portal doesn't answer like Avature."""
    jobs: dict[str, dict[str, str]] = {}
    for page in range(max_pages):
        found = cards(http.get_text(search_url(slug, page * PER_PAGE)) or "")
        if not found:
            return None if page == 0 else list(jobs.values())
        new = [c for c in found if c["id"] not in jobs]
        jobs.update((c["id"], c) for c in new)
        if not new or len(found) < PER_PAGE:
            break
    return list(jobs.values())


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    found = listed(http, slug, LIST_PAGES)
    return None if found is None else [c["title"] for c in found]


def _india_rank(text: str) -> int | None:
    """0 = the card names India, 1 = names no country, None = clearly elsewhere."""
    countries = extract_location(text).countries
    if "India" in countries:
        return 0
    return 1 if not countries else None


def fetch(http: HttpClient, company: Company) -> list[Job]:
    keep = []
    for card in listed(http, company.slug) or []:
        if not could_be_target(card["title"]):
            continue
        rank = _india_rank(card["text"]) if company.india_only else 0
        if rank is not None:
            keep.append((rank, card))
    keep.sort(key=lambda rc: rc[0])  # stable: page order (newest first) within each rank
    jobs = []
    for _, card in keep[:MAX_DETAILS]:
        job = parse_page(http.get_text(card["url"], fresh_days=DETAIL_FRESH_DAYS) or "", card["url"], company)
        if job:
            jobs.append(job)
    return jobs


def parse_page(html: str, url: str, company: Company) -> Job | None:
    job = careersite.parse_page(html, url, company)
    if job is None:
        return None
    job.source = NAME
    job_id = parse_qs(urlparse(url).query).get("jobId")
    if job_id:
        job.external_id = job_id[0]
    return job
