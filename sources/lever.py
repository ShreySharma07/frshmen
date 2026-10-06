"""Lever postings API: one call returns every published posting."""

from __future__ import annotations

from typing import Any

from sources.http import HttpClient
from sources.models import Company, Job
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "lever"


def url_for(slug: str) -> str:
    return f"https://api.lever.co/v0/postings/{slug}?mode=json"


def fetch(http: HttpClient, company: Company) -> list[Job]:
    return parse(http.get_json(url_for(company.slug)), company)


def parse(payload: Any, company: Company) -> list[Job]:
    if not isinstance(payload, list):
        return []
    jobs = []
    for raw in payload:
        cats = raw.get("categories") or {}
        locations = cats.get("allLocations") or ([cats["location"]] if cats.get("location") else [])
        jobs.append(Job(
            source=NAME,
            external_id=str(raw["id"]),
            company=company.name,
            company_slug=company.slug,
            title=(raw.get("text") or "").strip(),
            url=raw.get("hostedUrl") or "",
            location_raw=" / ".join(locations),
            description_text=_description(raw),
            posted_at=to_utc_iso(raw.get("createdAt")),
            department=cats.get("department") or cats.get("team"),
            employment_type=cats.get("commitment"),
            ats_workplace_type=raw.get("workplaceType") or None,
            ats_countries=[raw["country"]] if raw.get("country") else [],
        ))
    return jobs


def _description(raw: dict[str, Any]) -> str:
    """Lever splits a posting into an intro, titled lists (often "Requirements"), and a closing note.

    Requirements frequently live only in `lists`, so dropping them would hide the YoE line.
    """
    parts = [html_to_text(raw.get("description")) or (raw.get("descriptionPlain") or "").strip()]
    for section in raw.get("lists") or []:
        heading = (section.get("text") or "").strip()
        body = html_to_text(section.get("content"))
        parts.append(f"{heading}\n{body}" if heading else body)
    parts.append(html_to_text(raw.get("additional")) or (raw.get("additionalPlain") or "").strip())
    return "\n\n".join(p for p in parts if p)
