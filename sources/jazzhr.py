"""JazzHR career pages (<slug>.applytojob.com): JazzHR's public XML export of open jobs.

https://app.jazz.co/feeds/export/jobs/<slug> needs no key (the feed JazzHR's help centre
documents for career pages) and carries every open job with its full description.
"""

from __future__ import annotations

from sources import xmlfeed
from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import experience_line
from sources.text import html_to_text

NAME = "jazzhr"


def url_for(slug: str) -> str:
    return f"https://app.jazz.co/feeds/export/jobs/{slug}"


def _feed(http: HttpClient, slug: str) -> str | None:
    xml = http.get_text(url_for(slug), accept="application/xml,text/xml;q=0.9,*/*;q=0.8")
    return xml if xml and "<jobs" in xml else None


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    xml = _feed(http, slug)
    return None if xml is None else [xmlfeed.field(j, "title") for j in xmlfeed.records(xml, "job")
                                     if xmlfeed.field(j, "status").lower() in ("", "open")]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(_feed(http, company.slug) or "", company)


def parse(xml: str, company: Company) -> list[Job]:
    jobs = []
    for job in xmlfeed.records(xml, "job"):
        if xmlfeed.field(job, "status").lower() not in ("", "open"):
            continue
        title, url = xmlfeed.field(job, "title"), xmlfeed.field(job, "url")
        if not title or not url:
            continue
        place = ", ".join(p for p in (xmlfeed.field(job, k) for k in ("city", "state", "country")) if p)
        text = html_to_text(xmlfeed.field(job, "description"))
        # JazzHR's own experience field ("Entry Level", "Experienced") is kept where the YoE reader sees it.
        level = experience_line(xmlfeed.field(job, "experience"))
        jobs.append(Job(
            source=NAME,
            external_id=xmlfeed.field(job, "id") or url,
            company=company.name,
            company_slug=company.slug,
            title=title,
            url=url,
            location_raw=place,
            description_text="\n".join(t for t in (text, level) if t),
            department=xmlfeed.field(job, "department") or None,
            employment_type=xmlfeed.field(job, "type") or None,
        ))
    return jobs
