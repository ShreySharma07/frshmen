"""Teamtailor career sites: the public RSS feed every site publishes at /jobs.rss.

Slug: the career site's host, a Teamtailor subdomain ("acme.teamtailor.com") or the company's own
("careers.cerrion.com"). The feed gives each job's full description, places and remote status.
"""

from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime

from sources import xmlfeed
from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text

NAME = "teamtailor"
PER_PAGE = 100

_REMOTE = {"fully": "remote", "temporary": "remote", "hybrid": "hybrid", "none": "onsite"}


def url_for(slug: str, page: int = 1) -> str:
    return f"https://{slug}/jobs.rss?per_page={PER_PAGE}&page={page}"


def _items(http: HttpClient, slug: str) -> list[str] | None:
    """Every <item>, page by page. None when the host has no Teamtailor feed."""
    items: list[str] = []
    for page in range(1, 11):
        xml = http.get_text(url_for(slug, page), accept="application/rss+xml,application/xml;q=0.9,*/*;q=0.8")
        if xml is None or "<rss" not in xml:
            return None if page == 1 else items
        batch = xmlfeed.records(xml, "item")
        items += batch
        if len(batch) < PER_PAGE:
            break
    return items


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    items = _items(http, slug)
    return None if items is None else [xmlfeed.field(i, "title") for i in items]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(_items(http, company.slug) or [], company)


def _date(value: str) -> str | None:
    """RSS dates ("Sun, 08 Nov 2026 20:32:20 +0100") as ISO UTC."""
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse(items: list[str], company: Company) -> list[Job]:
    jobs = []
    for item in items:
        places = []
        for loc in xmlfeed.records(item, "tt:location"):
            place = ", ".join(p for p in (xmlfeed.field(loc, "tt:city"), xmlfeed.field(loc, "tt:country")) if p)
            if place:
                places.append(place)
        remote = _REMOTE.get(xmlfeed.field(item, "remoteStatus").lower())
        title, url = xmlfeed.field(item, "title"), xmlfeed.field(item, "link")
        if not title or not url:
            continue
        jobs.append(Job(
            source=NAME,
            external_id=xmlfeed.field(item, "guid") or url.rstrip("/").rsplit("/", 1)[-1],
            company=company.name,
            company_slug=company.slug,
            title=title,
            url=url,
            location_raw=" / ".join(dict.fromkeys(places)) or ("Remote" if remote == "remote" else ""),
            description_text=html_to_text(xmlfeed.field(item, "description")),
            posted_at=_date(xmlfeed.field(item, "pubDate")),
            department=xmlfeed.field(item, "tt:department") or None,
            ats_workplace_type=remote,
        ))
    return jobs

