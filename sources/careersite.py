"""Company career sites without a JSON API: the sitemap lists job pages, each page carries schema.org data.

Covers SAP SuccessFactors career sites (EY, Capgemini, HCLTech, Globant...) and any site that
marks its job pages up for Google's job search. Slug: the site's host, optionally with the
sitemap path ("careers.ey.com" -> https://careers.ey.com/sitemap.xml). robots.txt on these
sites allows the sitemap and job pages; their RSS feeds under /services/ are disallowed, so
they aren't used.

Job URLs carry the location and title as words ("/ey/job/Bengaluru-Associate-.../1423670533/"),
so India and target-role screening happens before any page is fetched. A page gives the job
as JSON-LD ("@type": "JobPosting") or as microdata (itemprop="title", "description",
"datePosted", "addressLocality"...); both are read.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urlparse

from extract.location import extract_location
from extract.profile import load_profile
from extract.role import match_role
from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "careersite"
MAX_DETAILS = 150  # job pages per board per run, newest first
DETAIL_FRESH_DAYS = 3  # job text rarely changes; later runs fetch only new pages
MAX_CHILD_SITEMAPS = 10
_JOB_PATH = re.compile(r"/jobs?/", re.I)
_ENTRY = re.compile(r"<url>\s*<loc>\s*([^<]+?)\s*</loc>(?:\s*<lastmod>\s*([^<]+?)\s*</lastmod>)?", re.I)
_ID = re.compile(r"/(\d{5,})/?$")


def sitemap_url(slug: str) -> str:
    return f"https://{slug}" if "/" in slug else f"https://{slug}/sitemap.xml"


def _words(url: str) -> str:
    """"/ey/job/Bengaluru-Associate-SaT-TMT/1423670533/" -> "Bengaluru Associate SaT TMT"."""
    path = unquote(unescape(urlparse(url).path))
    tail = path.split("/job/", 1)[-1] if "/job/" in path else path
    return re.sub(r"[-_/+]+|\d{5,}", " ", tail).strip()


def job_entries(http: HttpClient, slug: str) -> list[tuple[str, str]]:
    """(job URL, lastmod) for every job page in the sitemap, following one level of sitemap index."""
    root = http.get_text(sitemap_url(slug), accept="application/xml,text/xml;q=0.9,*/*;q=0.8") or ""
    bodies = [root]
    if "<sitemapindex" in root:
        children = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", root)[:MAX_CHILD_SITEMAPS]
        bodies = [http.get_text(unescape(u), accept="application/xml,text/xml;q=0.9,*/*;q=0.8") or "" for u in children]
    seen: dict[str, str] = {}
    for body in bodies:
        for loc, lastmod in _ENTRY.findall(body):
            url = unescape(loc)
            if _JOB_PATH.search(urlparse(url).path):
                seen.setdefault(url, lastmod or "")
    return list(seen.items())


def _title_could_fit(words: str) -> bool:
    """The role rules on the URL's words alone. Families the description must confirm (plain
    SWE, Python backend, Android) still pass; excluded titles and non-target roles don't. Stricter
    than sources/prefilter, because these boards list thousands of tax and audit roles."""
    m = match_role(words, "", load_profile())
    return m.is_target or m.family is not None


def screen(entries: list[tuple[str, str]], india_only: bool) -> list[str]:
    """Job URLs worth a page fetch: titles that could fit (and India for india_only boards), newest first."""
    keep = []
    for url, lastmod in entries:
        words = _words(url)
        if not _title_could_fit(words):
            continue
        if india_only and "India" not in extract_location(words).countries:
            continue
        keep.append((lastmod, url))
    return [url for _, url in sorted(keep, key=lambda e: e[0], reverse=True)]


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    entries = job_entries(http, slug)
    return [_words(url) for url, _ in entries] if entries else None


def fetch(http: HttpClient, company: Company) -> list[Job]:
    jobs = []
    for url in screen(job_entries(http, company.slug), company.india_only)[:MAX_DETAILS]:
        job = parse_page(http.get_text(url, fresh_days=DETAIL_FRESH_DAYS) or "", url, company)
        if job:
            jobs.append(job)
    return jobs


# --- Page parsing ----------------------------------------------------------------------------


class _Microdata(HTMLParser):
    """Collects schema.org JobPosting microdata: meta content values and element text by itemprop."""

    TEXT_PROPS = {"title", "description"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.props: dict[str, str] = {}
        self._capture: list[list[Any]] = []  # [prop, tag, depth, parts]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        for cap in self._capture:
            if tag == cap[1]:
                cap[2] += 1
            cap[3].append(self.get_starttag_text() or "")
        prop = a.get("itemprop")
        if not prop:
            return
        if a.get("content") is not None:
            self.props.setdefault(prop, a["content"] or "")
        elif prop in self.TEXT_PROPS and prop not in self.props and tag not in ("meta", "link"):
            self._capture.append([prop, tag, 1, []])

    def handle_endtag(self, tag: str) -> None:
        for cap in list(self._capture):
            if tag == cap[1]:
                cap[2] -= 1
                if cap[2] == 0:
                    self.props[cap[0]] = "".join(cap[3])
                    self._capture.remove(cap)
                    continue
            cap[3].append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        for cap in self._capture:
            cap[3].append(data.replace("<", "&lt;"))


def _jsonld_posting(html: str) -> dict[str, Any] | None:
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            kind = item.get("@type") if isinstance(item, dict) else None
            if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                return item
    return None


def _date(value: str | None) -> str | None:
    """ISO dates, or SuccessFactors' "Sat Oct 03 02:00:00 UTC 2026"."""
    if not value:
        return None
    iso = to_utc_iso(value.strip())
    if iso:
        return iso
    try:
        dt = datetime.strptime(value.strip(), "%a %b %d %H:%M:%S UTC %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _place(address: Any) -> str:
    if not isinstance(address, dict):
        return str(address or "")
    parts = [address.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
    return ", ".join(str(p.get("name") if isinstance(p, dict) else p) for p in parts if p)


def parse_page(html: str, url: str, company: Company) -> Job | None:
    posting = _jsonld_posting(html)
    if posting:
        locs = posting.get("jobLocation") or []
        locs = locs if isinstance(locs, list) else [locs]
        location = " / ".join(p for p in (_place(loc.get("address") if isinstance(loc, dict) else loc) for loc in locs) if p)
        if posting.get("jobLocationType") == "TELECOMMUTE":
            location = f"{location} / Remote" if location else "Remote"
        ident = posting.get("identifier")
        ident = ident.get("value") if isinstance(ident, dict) else ident
        title, description = posting.get("title"), posting.get("description")
        posted, employment = posting.get("datePosted"), posting.get("employmentType")
    else:
        md = _Microdata()
        md.feed(html)
        p = md.props
        title, description, posted, employment, ident = (p.get("title"), p.get("description"), p.get("datePosted"),
                                                          p.get("employmentType"), None)
        location = ", ".join(x for x in (p.get("addressLocality"), p.get("addressRegion"), p.get("addressCountry")) if x)
    title = html_to_text(title or "").strip()
    if not title or not description:
        return None
    m = _ID.search(urlparse(url).path)
    return Job(
        source=NAME,
        external_id=str(ident or (m.group(1) if m else urlparse(url).path.strip("/"))),
        company=company.name,
        company_slug=company.slug,
        title=title[:200],
        url=url,
        location_raw=location,
        description_text=html_to_text(description),
        posted_at=_date(posted),
        employment_type=", ".join(employment) if isinstance(employment, list) else employment,
    )
