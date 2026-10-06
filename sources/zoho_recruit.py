"""Zoho Recruit careers sites: the careers page lists jobs; each job page carries its full record.

Slug: the careers host, e.g. "wadhwaniai.zohorecruit.in" or a custom domain like
"career.qure.ai". The list page embeds the open jobs in `<input id="jobs" value="[...]">`
with only title, city and type; each job page embeds the full record (description,
Work_Experience, Date_Opened) as a JavaScript string literal. Both are in the HTML
before any script runs, and Zoho's robots.txt allows `/jobs/*`. Job pages are large
(~2 MB), so only jobs whose title could be a target role are opened.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.prefilter import could_be_target, experience_line
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "zoho_recruit"
MAX_DETAILS = 60
DETAIL_FRESH_DAYS = 3
_JOBS_INPUT = re.compile(r"<input[^>]*\bid=[\"']jobs[\"'][^>]*>", re.I)
_VALUE = re.compile(r"\bvalue=(\"([^\"]*)\"|'([^']*)')", re.I)
# A single-quoted JS string holding a JSON array of records: '[{...}]'
_JS_ARRAY = re.compile(r"'(\[\{(?:[^'\\]|\\.)*\}\])'")
_JS_ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)", re.S)
_JS_SIMPLE = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def page_url(slug: str) -> str:
    return f"https://{slug}/jobs/Careers"


def job_page_url(slug: str, job_id: str) -> str:
    return f"https://{slug}/jobs/Careers/{job_id}"


def embedded_jobs(page: str | None) -> list[dict[str, Any]] | None:
    """The list page's `<input id="jobs">` array, or None if the page has none."""
    tag = _JOBS_INPUT.search(page or "")
    value = _VALUE.search(tag.group(0)) if tag else None
    if not value:
        return None
    try:
        data = json.loads(html.unescape(value.group(2) if value.group(2) is not None else value.group(3)))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def _js_unescape(literal: str) -> str:
    def one(m: re.Match[str]) -> str:
        esc = m.group(1)
        if esc[0] in "xu" and len(esc) > 1:
            return chr(int(esc[1:], 16))
        return _JS_SIMPLE.get(esc, esc)
    return _JS_ESCAPE.sub(one, literal)


def job_record(page: str | None, job_id: str) -> dict[str, Any]:
    """The full record for `job_id` from a job page's embedded JS array; {} if not found."""
    for m in _JS_ARRAY.finditer(page or ""):
        if "Job_Description" not in m.group(1) and "Job\\_Description" not in m.group(1):
            continue
        try:
            rows = json.loads(_js_unescape(m.group(1)))
        except json.JSONDecodeError:
            continue
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and str(row.get("id")) == str(job_id):
                return row
    return {}


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    jobs = embedded_jobs(http.get_text(page_url(slug)))
    return None if jobs is None else [_title(j) for j in jobs]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    listed = [j for j in embedded_jobs(http.get_text(page_url(company.slug))) or []
              if _truthy(j.get("Publish"), default=True) and could_be_target(_title(j))]
    jobs = []
    for item in listed[:MAX_DETAILS]:
        detail = job_record(http.get_text(job_page_url(company.slug, item["id"]), fresh_days=DETAIL_FRESH_DAYS), item["id"])
        jobs.append(parse_one({**item, **detail}, company))
    return jobs


def _title(raw: dict[str, Any]) -> str:
    return str(raw.get("Posting_Title") or raw.get("Job_Opening_Name") or "").strip()


def _truthy(value: Any, default: bool = False) -> bool:
    # Zoho sends booleans in the job record but "True"/"False" strings in the list input.
    if value is None or value == "":
        return default
    return value is True or str(value).strip().lower() in ("true", "yes", "1")


def parse(payload: Any, company: Company) -> list[Job]:
    """Records already holding everything (tests, or a list page that carries full records)."""
    if not isinstance(payload, list):
        return []
    return [parse_one(raw, company) for raw in payload if _truthy(raw.get("Publish"), default=True)]


def parse_one(raw: dict[str, Any], company: Company) -> Job:
    title = _title(raw)
    place = ", ".join(str(raw[k]) for k in ("City", "State", "Country") if raw.get(k))
    remote = _truthy(raw.get("Remote_Job"))
    slugified = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")
    experience = raw.get("Work_Experience") or raw.get("Experience")
    return Job(
        source=NAME,
        external_id=str(raw["id"]),
        company=company.name,
        company_slug=company.slug,
        title=title,
        url=f"https://{company.slug}/jobs/Careers/{raw['id']}/{slugified}",
        location_raw=place + (" (Remote)" if remote and place else "Remote" if remote else ""),
        description_text="\n\n".join(p for p in [experience_line(experience), html_to_text(raw.get("Job_Description"))] if p),
        posted_at=to_utc_iso(raw.get("Date_Opened")),
        department=raw.get("Industry") or None,
        employment_type=raw.get("Job_Type") or None,
        ats_workplace_type="remote" if remote else None,
    )
