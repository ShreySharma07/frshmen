"""Hacker News "Ask HN: Who is hiring?": the monthly thread, through HN's official Algolia API.

Each top-level comment is one company's post, by convention starting with a header line
like "Acme AI | ML Engineer | Bangalore, India | ONSITE | https://acme.ai/jobs". Only the
latest thread is read. Slug: "whoishiring" (the account that posts the threads).
"""

from __future__ import annotations

import re
from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "hn"
SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=6"
THREAD_TITLE = "Ask HN: Who is hiring?"
# A header part that names a role, used to pick the title out of "Company | Role | Place | ...".
_ROLE = re.compile(r"engineer|developer|scientist|researcher|\bml\b|\bai\b|intern|analyst|architect|"
                   r"designer|manager|lead|founding|sre|devops|programmer|\bswe\b|\bsde\b", re.I)
_URL = re.compile(r"https?://\S+|\b[\w-]+\.(?:com|ai|io|co|dev|org|net|app)\b\S*", re.I)


def item_url(item_id: Any) -> str:
    return f"https://hn.algolia.com/api/v1/items/{item_id}"


def latest_thread(http: HttpClient) -> dict[str, Any] | None:
    hits = (http.get_json(SEARCH_URL) or {}).get("hits") or []
    thread = next((h for h in hits if (h.get("title") or "").startswith(THREAD_TITLE)), None)
    return http.get_json(item_url(thread["objectID"])) if thread else None


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    thread = latest_thread(http)
    return None if thread is None else [j.title for j in parse(thread, Company("HN", NAME, slug))]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(latest_thread(http) or {}, company)


def header_parts(text: str) -> list[str]:
    """The "a | b | c" header of a post, split; [] when the post doesn't use the convention."""
    first = re.split(r"<p>", text or "", maxsplit=1)[0]
    line = html_to_text(first).strip().splitlines()[0] if html_to_text(first).strip() else ""
    parts = [p.strip() for p in line.split("|") if p.strip()]
    return parts if len(parts) >= 2 else []


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, dict):
        return []
    jobs = []
    for post in payload.get("children") or []:
        text = post.get("text")
        parts = header_parts(text)
        if not text or not parts:
            continue  # deleted, or a reply-style comment rather than a job post
        # "Acme AI (https://acme.ai)" -> "Acme AI": drop bracketed asides first, then bare links.
        name = _URL.sub("", re.sub(r"\s*\(.*?\)", "", parts[0])).strip() or parts[0]
        rest = [p for p in parts[1:] if not _URL.fullmatch(p)]
        title = next((p for p in rest if _ROLE.search(p)), rest[0] if rest else "")
        if not title:
            continue
        jobs.append(Job(
            source=NAME,
            external_id=str(post["id"]),
            company=name,
            company_slug=company.slug,
            title=title[:200],
            url=f"https://news.ycombinator.com/item?id={post['id']}",
            # Everything else in the header (place, REMOTE/ONSITE, visa notes) feeds the location rules.
            location_raw=" | ".join(p for p in rest if p is not title),
            description_text=html_to_text(text),
            posted_at=to_utc_iso(post.get("created_at")),
        ))
    return jobs
