"""Hacker News "Ask HN: Who is hiring?": the monthly thread, through HN's official Algolia API.

Each top-level comment is one company's post, by convention starting with a header line
like "Acme AI | ML Engineer | Bangalore, India | ONSITE | https://acme.ai/jobs". Only the
latest thread is read. Slug: "whoishiring" (the account that posts the threads).

People looking for work sometimes post their own profile in the hiring thread, in the same
"Name | Role | Place" shape. Those are skipped (`is_candidate_post`): a profile shown as a job
is a wrong result, a missed post is only a missed job.
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


# The fields of the "Who wants to be hired?" template. No company's post has them.
_SEEKER_TEMPLATE = re.compile(r"willing to relocate\s*:|r[ée]sum[ée]\s*(?:/\s*cv)?\s*:|\bcv\s*:", re.I)
# A person describing themselves or what they are looking for.
_SELF = re.compile(
    r"\bI(?:'m|’m| am)\s+(?:an?\b|looking\b|seeking\b|open to\b|currently\b)|"
    r"\b(?:seeking|looking for)\s+(?:an?\s+)?(?:new\s+|next\s+|full[- ]time\s+|remote\s+)*(?:role|position|job|work|opportunit)|"
    r"\bmy\s+(?:resume|r[ée]sum[ée]|cv|portfolio|github)\b|\bopen to work\b|\bavailable for (?:hire|work)\b", re.I)
# An employer speaking: any of these means the post is an opening, even when a founder writes "I".
_EMPLOYER = re.compile(r"\bwe\b|\bwe['’](?:re|ve|ll)\b|\bour\b|\bhiring\b|\bapply\b|\bjoin (?:us|me|the team)\b|"
                       # "looking for a backend engineer", but not "looking for a new role".
                       r"\blooking for (?!(?:an?\s+)?(?:\w+[- ]){0,4}(?:role|position|job|work|opportunit))"
                       r"(?:an?|\d+|two|three|several|experienced|senior|junior|talented|strong)\b", re.I)


def is_candidate_post(text: str) -> bool:
    """True for someone's own profile rather than an opening: the job-seekers' template, or a
    first-person description with nothing an employer would say."""
    if _SEEKER_TEMPLATE.search(text):
        return True
    return bool(_SELF.search(text)) and not _EMPLOYER.search(text)


def item_url(item_id: Any) -> str:
    return f"https://hn.algolia.com/api/v1/items/{item_id}"


def recent_threads(http: HttpClient, count: int = 1) -> list[dict[str, Any]]:
    """The newest `count` "Who is hiring?" threads, newest first, with their comments."""
    hits = (http.get_json(SEARCH_URL) or {}).get("hits") or []
    threads = [h for h in hits if (h.get("title") or "").startswith(THREAD_TITLE)][:count]
    return [t for t in (http.get_json(item_url(h["objectID"])) for h in threads) if t]


def latest_thread(http: HttpClient) -> dict[str, Any] | None:
    threads = recent_threads(http)
    return threads[0] if threads else None


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


def company_name(parts: list[str]) -> str:
    # "Acme AI (https://acme.ai)" -> "Acme AI": drop bracketed asides first, then bare links.
    return _URL.sub("", re.sub(r"\s*\(.*?\)", "", parts[0])).strip() or parts[0]


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, dict):
        return []
    jobs = []
    for post in payload.get("children") or []:
        text = post.get("text")
        parts = header_parts(text)
        if not text or not parts:
            continue  # deleted, or a reply-style comment rather than a job post
        if is_candidate_post(html_to_text(text)):
            continue
        name = company_name(parts)
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
