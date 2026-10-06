"""Eightfold careers sites (Microsoft, Qualcomm, PayPal, NetApp, Netflix...): the JSON the site calls.

Slug: "<host>/<domain>", e.g. "apply.careers.microsoft.com/microsoft.com". Two kinds of tenant:
older ones answer the v2 list (descriptions included); newer "PCSX" ones refuse it (403) and
answer a search endpoint without descriptions, so those come from the per-job v2 call, which
both kinds serve. Only India is requested, as for every MNC board.
"""

from __future__ import annotations

from typing import Any

from sources.http import FetchError, HttpClient
from sources.models import Company, Job
from sources.prefilter import could_be_target
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "eightfold"
V2_PAGE = 50
PCSX_PAGE = 10  # fixed by the endpoint
MAX_PAGES = 60
MAX_DETAILS = 150
LOCATION = "India"
_WORK_MODE = {"onsite": "onsite", "on-site": "onsite", "remote": "remote", "hybrid": "hybrid"}


def _parts(slug: str) -> tuple[str, str]:
    host, _, domain = slug.partition("/")
    return host, domain


def v2_url(slug: str, start: int) -> str:
    host, domain = _parts(slug)
    return f"https://{host}/api/apply/v2/jobs?domain={domain}&location={LOCATION}&start={start}&num={V2_PAGE}"


def pcsx_url(slug: str, start: int) -> str:
    host, domain = _parts(slug)
    return f"https://{host}/api/pcsx/search?domain={domain}&query=&location={LOCATION}&start={start}"


def detail_url(slug: str, job_id: Any) -> str:
    host, domain = _parts(slug)
    return f"https://{host}/api/apply/v2/jobs/{job_id}?domain={domain}"


def _paged(http: HttpClient, url, page_size: int, unwrap) -> list[dict[str, Any]] | None:
    first = unwrap(http.get_json(url(0)))
    if first is None:
        return None
    positions, total = first
    page = 1
    while len(positions) < total and page < MAX_PAGES:
        more = unwrap(http.get_json(url(page * page_size)))
        if not more or not more[0]:
            break
        positions += more[0]
        page += 1
    return positions


def _v2(payload: Any) -> tuple[list[dict[str, Any]], int] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("positions"), list):
        return None
    return list(payload["positions"]), int(payload.get("count") or 0)


def _pcsx(payload: Any) -> tuple[list[dict[str, Any]], int] | None:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("positions"), list):
        return None
    return list(data["positions"]), int(data.get("count") or 0)


def list_positions(http: HttpClient, slug: str) -> tuple[str, list[dict[str, Any]]] | None:
    """("v2" | "pcsx", positions) for this tenant, or None if neither answers."""
    try:
        positions = _paged(http, lambda s: v2_url(slug, s), V2_PAGE, _v2)
        if positions is not None:
            return "v2", positions
    except FetchError as e:
        if "HTTP 403" not in str(e):  # PCSX tenants refuse the v2 list with a 403
            raise
    positions = _paged(http, lambda s: pcsx_url(slug, s), PCSX_PAGE, _pcsx)
    return ("pcsx", positions) if positions is not None else None


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    found = list_positions(http, slug)
    return None if found is None else [(p.get("name") or p.get("posting_name") or "").strip() for p in found[1]]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    found = list_positions(http, company.slug)
    if not found:
        return []
    kind, positions = found
    positions = [p for p in positions if could_be_target(p.get("name") or "")]
    jobs = []
    for pos in positions[:MAX_DETAILS]:
        detail = pos if kind == "v2" and pos.get("job_description") else http.get_json(detail_url(company.slug, pos["id"]))
        jobs.append(parse(pos, detail if isinstance(detail, dict) else {}, company))
    return jobs


def parse(pos: dict[str, Any], detail: dict[str, Any], company: Company) -> Job:
    host, _ = _parts(company.slug)
    raw = {**pos, **detail}
    locations = raw.get("locations") or ([raw["location"]] if raw.get("location") else [])
    url = raw.get("canonicalPositionUrl") or raw.get("positionUrl") or ""
    if url.startswith("/"):
        url = f"https://{host}{url}"
    created = raw.get("t_create") or raw.get("postedTs") or raw.get("creationTs")
    mode = str(raw.get("work_location_option") or raw.get("workLocationOption") or "").lower()
    return Job(
        source=NAME,
        external_id=str(raw.get("display_job_id") or raw.get("displayJobId") or raw["id"]),
        company=company.name,
        company_slug=company.slug,
        title=(raw.get("name") or raw.get("posting_name") or "").strip(),
        url=url or f"https://{host}/careers/job/{raw['id']}",
        location_raw=" / ".join(dict.fromkeys(str(loc).strip() for loc in locations if str(loc).strip())),
        description_text=html_to_text(raw.get("job_description")),
        # Eightfold timestamps are epoch seconds.
        posted_at=to_utc_iso(int(created) * 1000) if str(created or "").isdigit() else None,
        department=raw.get("department") or None,
        ats_workplace_type=_WORK_MODE.get(mode),
    )
