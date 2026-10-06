"""Fetch every verified company's board and write classified jobs to data/jobs.json.

fetch -> normalize -> dedupe -> classify (fresher / maybe / experienced, with
evidence). D1 publishing comes later. One broken board never stops the others.

Run: python scripts/fetch_jobs.py [--limit N] [--company NAME ...] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `sources` imports when run as a plain script

import yaml  # noqa: E402

from extract.classify import classify  # noqa: E402
from extract.eligibility import check_eligibility  # noqa: E402
from extract.location import REMOTE_UNSPECIFIED, extract_location  # noqa: E402
from extract.profile import load_profile  # noqa: E402
from extract.role import match_role  # noqa: E402
from extract.visa import extract_visa  # noqa: E402
from sources import ADAPTERS  # noqa: E402
from sources.http import FetchError, HttpClient  # noqa: E402
from sources.models import Company, Job  # noqa: E402

COMPANIES = ROOT / "config" / "companies.yaml"
DEFAULT_OUT = ROOT / "data" / "jobs.json"
CACHE_DIR = ROOT / ".cache" / "http"


def load_companies(path: Path = COMPANIES) -> list[Company]:
    """Companies with a verified, non-empty board on an ATS we have an adapter for."""
    out = []
    for c in yaml.safe_load(path.read_text())["companies"]:
        if c.get("verified") and c.get("jobs") and c.get("ats") in ADAPTERS:
            out.append(Company(name=c["name"], ats=c["ats"], slug=str(c["slug"]), category=c.get("category", ""),
                               india_only=bool(c.get("india_only"))))
    return out


def location_fields(job: Job, hide_onsite_only_in: frozenset[str] = frozenset({"bengaluru", "hyderabad"})) -> dict:
    loc = extract_location(job.location_raw, job.ats_countries)
    # The ATS's structured workplace type wins; "or Remote" in the text is the fallback.
    location_type = job.ats_workplace_type or ("remote" if loc.remote else None)
    visa = extract_visa(job.description_text)
    fit = check_eligibility(loc.countries, loc.cities, location_type, visa, hide_onsite_only_in)
    return {"countries": loc.countries, "cities": loc.cities, "location_type": location_type,
            "location_evidence": loc.evidence + visa.evidence, "visa_sponsorship": visa.sponsorship,
            "eligible": fit.eligible, "eligibility_reason": fit.reason}


def in_india_or_remote(job: Job) -> bool:
    """For india_only boards: keep India and location-free remote roles, drop the rest before classifying."""
    loc = extract_location(job.location_raw, job.ats_countries)
    return "India" in loc.countries or loc.countries == [REMOTE_UNSPECIFIED] or not loc.countries


def dedupe(jobs: list[Job]) -> list[Job]:
    """Drop repeats by id, then cross-posts of the same role (skills.md §4)."""
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    out = []
    for job in jobs:
        if job.id in seen_ids or job.dedupe_key in seen_keys:
            continue
        seen_ids.add(job.id)
        seen_keys.add(job.dedupe_key)
        out.append(job)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="only the first N companies (smoke tests)")
    parser.add_argument("--company", nargs="*", help="only these company names")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-cache", action="store_true", help="skip ETag/If-Modified-Since cache")
    parser.add_argument("--workers", type=int, default=8, help="boards fetched in parallel (different hosts)")
    args = parser.parse_args()

    companies = load_companies()
    if args.company:
        companies = [c for c in companies if c.name in set(args.company)]
    if args.limit:
        companies = companies[: args.limit]

    http = HttpClient(cache_dir=None if args.no_cache else CACHE_DIR)
    started = time.monotonic()
    jobs: list[Job] = []
    errors: dict[str, str] = {}
    per_company: dict[str, int] = {}
    def fetch_one(company: Company) -> tuple[Company, list[Job] | None, str | None]:
        try:
            found = ADAPTERS[company.ats].fetch(http, company)
        except FetchError as e:
            return company, None, str(e)
        except (KeyError, TypeError, ValueError) as e:
            # The ATS changed its payload shape: report it, keep going.
            return company, None, f"parse error: {e!r}"
        if company.india_only:
            found = [j for j in found if in_india_or_remote(j)]
        return company, found, None

    # Boards on different hosts are fetched in parallel; HttpClient still spaces requests per host.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, (company, found, error) in enumerate(pool.map(fetch_one, companies), 1):
            if error is not None:
                errors[company.name] = error
                print(f"[{i}/{len(companies)}] {company.name}: FAILED ({error})", flush=True)
                continue
            per_company[company.name] = len(found)
            jobs.extend(found)
            print(f"[{i}/{len(companies)}] {company.name}: {len(found)} jobs", flush=True)

    unique = dedupe(jobs)
    profile = load_profile()
    records = [
        {
            **j.to_dict(),
            **classify(j.title, j.description_text, set(profile.exact_batch), set(profile.soft_batch)).to_dict(),
            **match_role(j.title, j.description_text, profile).to_dict(),
            **location_fields(j, profile.hide_onsite_only_in or frozenset({"bengaluru", "hyderabad"})),
        }
        for j in unique
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        # Boards that answered: publish_d1.py only closes missing jobs from these.
        "boards_ok": [{"source": c.ats, "company_slug": c.slug} for c in companies if c.name in per_company],
        "errors": errors,
        "jobs": records,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))

    # Run summary (skills.md §7): fetched, kept, per-source errors.
    print(f"\nCompanies: {len(companies)} ok={len(per_company)} failed={len(errors)}")
    print(f"Jobs: fetched={len(jobs)} after_dedupe={len(unique)} -> {args.out}")
    levels = Counter(r["level"] for r in records)
    print(f"Levels: fresher={levels['fresher']} maybe={levels['maybe']} experienced={levels['experienced']}")
    targets = [r for r in records if r["role_match"]]
    target_levels = Counter(r["level"] for r in targets)
    print(f"Target roles: {len(targets)} (fresher={target_levels['fresher']} maybe={target_levels['maybe']})")
    print(f"Took {time.monotonic() - started:.0f}s")
    for name, err in errors.items():
        print(f"  error: {name}: {err}")
    # Fail the run only if nothing worked; a few dead boards are normal.
    return 1 if companies and not per_company else 0


if __name__ == "__main__":
    sys.exit(main())
