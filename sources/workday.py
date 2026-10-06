"""Workday careers sites: the site's own job search lists jobs, one JSON call per job gives its text.

Slug format: "<tenant>/<wdN>/<site>", e.g. "browserstack/wd3/External" for
https://browserstack.wd3.myworkdayjobs.com/External. Listing uses the search the careers
page itself POSTs to (`/wday/cxs/.../jobs`), paged 20 at a time; for india_only boards
it applies the tenant's own India country facet. Many tenants' sitemaps stop at 100
URLs, so the sitemap is only the fallback when search fails. robots.txt doesn't exclude
either path.
"""

from __future__ import annotations

import re
from typing import Any

from sources.http import FetchError, HttpClient
from sources.models import Company, Job
from extract.location import REMOTE_UNSPECIFIED, extract_location
from sources.prefilter import could_be_target
from sources.text import html_to_text
from sources.timeutil import to_utc_iso

NAME = "workday"
# Per-run cap on detail requests per board; the title screen keeps real boards well under it.
MAX_DETAILS = 150
# Job text rarely changes: reuse a stored detail for this long, so later runs only fetch new jobs.
DETAIL_FRESH_DAYS = 3
SEARCH_PAGE = 20  # Workday answers larger pages with zero results
MAX_SEARCH_PAGES = 50  # 1,000 jobs per board per run
LIST_PAGES = 5  # the verifier only needs a sample
# Workday's reference id for India, seen in job JSON ("country": {"id": ...}) across tenants.
INDIA_COUNTRY_ID = "c4f78be1a8f14da0ab49ce1162348a5e"


def _parts(slug: str) -> tuple[str, str, str]:
    tenant, wd, site = slug.split("/")
    return tenant, wd, site


def sitemap_url(slug: str) -> str:
    tenant, wd, site = _parts(slug)
    return f"https://{tenant}.{wd}.myworkdayjobs.com/{site}/siteMap.xml"


def detail_url(slug: str, path: str) -> str:
    tenant, wd, site = _parts(slug)
    return f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{path}"


def search_url(slug: str) -> str:
    tenant, wd, site = _parts(slug)
    return f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"


def _search_body(offset: int, facets: dict[str, list[str]]) -> dict[str, Any]:
    return {"appliedFacets": facets, "limit": SEARCH_PAGE, "offset": offset, "searchText": ""}


def india_facet(facets: list[dict[str, Any]]) -> tuple[str, str] | None:
    """(facetParameter, value id) for India in a search response's facets, or None.

    Tenants name the facet differently ("locationCountry", "Location_Country", nested under
    "locationMainGroup"), so look for the India value wherever it is; prefer country facets.
    """
    found: list[tuple[str, str]] = []

    def walk(items: list[dict[str, Any]], param: str | None) -> None:
        for item in items or []:
            here = item.get("facetParameter") or param
            if item.get("descriptor") == "India" or item.get("id") == INDIA_COUNTRY_ID:
                if here and item.get("id"):
                    found.append((here, item["id"]))
            walk(item.get("values") or [], here)

    walk(facets, None)
    found.sort(key=lambda f: "country" not in f[0].lower())
    return found[0] if found else None


def search(http: HttpClient, slug: str, india_only: bool, max_pages: int = MAX_SEARCH_PAGES) -> list[dict[str, Any]] | None:
    """Job postings from the site's search, or None if the search isn't usable on this tenant."""
    first = http.post_json(search_url(slug), _search_body(0, {}))
    if not isinstance(first, dict) or not isinstance(first.get("jobPostings"), list):
        return None
    facets: dict[str, list[str]] = {}
    if india_only:
        india = india_facet(first.get("facets") or [])
        if india is None:
            return None  # can't filter by country here; the sitemap screen takes over
        facets = {india[0]: [india[1]]}
        first = http.post_json(search_url(slug), _search_body(0, facets))
        if not isinstance(first, dict) or not isinstance(first.get("jobPostings"), list):
            return None
    # Some tenants only report the total on the first page, so keep that one.
    total = int(first.get("total") or 0)
    postings = list(first["jobPostings"])
    page = 1
    while len(postings) < total and page < max_pages:
        more = http.post_json(search_url(slug), _search_body(page * SEARCH_PAGE, facets))
        if not isinstance(more, dict) or not more.get("jobPostings"):
            break
        postings += more["jobPostings"]
        page += 1
    return postings


def job_paths(sitemap: str, site: str) -> list[str]:
    """"/job/<location>/<Title>_<ReqId>" paths, in sitemap order."""
    paths = re.findall(rf"<loc>https://[^<]*?/{re.escape(site)}(/job/[^<]+)</loc>", sitemap)
    return list(dict.fromkeys(paths))


def title_from_path(path: str) -> str:
    """"/job/India-Remote/ML-Engineer_JR103661" -> "ML Engineer" (good enough for the title screen)."""
    last = path.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"_[A-Za-z]*\d[\w-]*$", "", last).replace("-", " ").strip()


def location_from_path(path: str) -> str:
    """"/job/India-Bangalore/ML-Engineer_R1" -> "India Bangalore"."""
    parts = path.strip("/").split("/")
    return parts[1].replace("-", " ") if len(parts) >= 3 else ""


def india_rank(path: str) -> int | None:
    """0 = path names India (or remote anywhere), 1 = no readable location, None = clearly elsewhere.

    Path location segments vary by tenant ("India-Bengaluru", "IN-KA-BANGALORE-...", "BangaloreIND",
    or none at all), so only a path that clearly names another country is skipped. fetch_jobs
    re-checks every fetched job against its full location.
    """
    countries = extract_location(location_from_path(path)).countries
    if "India" in countries or countries == [REMOTE_UNSPECIFIED]:
        return 0
    return 1 if not countries else None


def list_titles(http: HttpClient, slug: str) -> list[str] | None:
    try:
        postings = search(http, slug, india_only=False, max_pages=LIST_PAGES)
    except FetchError:
        postings = None
    if postings is not None:
        return [(p.get("title") or "").strip() for p in postings]
    sitemap = http.get_text(sitemap_url(slug))
    if sitemap is None or "<urlset" not in sitemap:
        return None
    return [title_from_path(p) for p in job_paths(sitemap, _parts(slug)[2])]


def search_paths(http: HttpClient, company: Company) -> list[str] | None:
    """Target-looking job paths from the site's search (India-filtered for india_only boards)."""
    try:
        postings = search(http, company.slug, company.india_only)
    except FetchError as e:
        # A tenant that refuses the search (403/405) still has its sitemap; other errors surface.
        if not any(code in str(e) for code in ("HTTP 403", "HTTP 405")):
            raise
        return None
    if postings is None:
        return None
    return [p["externalPath"] for p in postings
            if p.get("externalPath") and could_be_target(p.get("title") or "")]


def fetch(http: HttpClient, company: Company) -> list[Job]:
    paths = search_paths(http, company)
    if paths is None:
        paths = _sitemap_paths(http, company)
    jobs = []
    for path in paths[:MAX_DETAILS]:
        job = parse_detail(http.get_json(detail_url(company.slug, path), fresh_days=DETAIL_FRESH_DAYS), company)
        if job:
            jobs.append(job)
    return jobs


def _sitemap_paths(http: HttpClient, company: Company) -> list[str]:
    sitemap = http.get_text(sitemap_url(company.slug)) or ""
    paths = [p for p in job_paths(sitemap, _parts(company.slug)[2]) if could_be_target(title_from_path(p))]
    if company.india_only:
        # India paths first so the per-board cap is spent on them before unreadable ones.
        ranked = [(r, p) for p in paths if (r := india_rank(p)) is not None]
        paths = [p for _, p in sorted(ranked, key=lambda rp: rp[0])]
    return paths


def parse_detail(payload: Any, company: Company) -> Job | None:
    info = (payload or {}).get("jobPostingInfo") if isinstance(payload, dict) else None
    if not isinstance(info, dict) or not info.get("title"):
        return None
    locations = [info.get("location") or ""] + list(info.get("additionalLocations") or [])
    country = (info.get("country") or {}).get("descriptor")
    return Job(
        source=NAME,
        external_id=str(info.get("jobReqId") or info.get("jobPostingId") or info["id"]),
        company=company.name,
        company_slug=company.slug,
        title=info["title"].strip(),
        url=info.get("externalUrl") or "",
        location_raw=" / ".join(loc.strip() for loc in locations if loc and loc.strip()),
        description_text=html_to_text(info.get("jobDescription")),
        # startDate is the posting date; postedOn is only "Posted 30+ Days Ago".
        posted_at=to_utc_iso(info.get("startDate")),
        employment_type=info.get("timeType"),
        ats_countries=[country] if country else [],
    )
