"""Fetch every verified company's board and write normalized jobs to data/jobs.json.

Build step 1: fetch -> normalize -> dedupe. Extraction, classification and D1
publishing come later. One broken board never stops the others.

Run: python scripts/fetch_jobs.py [--limit N] [--company NAME ...] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `sources` imports when run as a plain script

import yaml  # noqa: E402

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
            out.append(Company(name=c["name"], ats=c["ats"], slug=str(c["slug"]), category=c.get("category", "")))
    return out


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
    for i, company in enumerate(companies, 1):
        try:
            found = ADAPTERS[company.ats].fetch(http, company)
        except FetchError as e:
            errors[company.name] = str(e)
            print(f"[{i}/{len(companies)}] {company.name}: FAILED ({e})", flush=True)
            continue
        except (KeyError, TypeError, ValueError) as e:
            # The ATS changed its payload shape: report it, keep going.
            errors[company.name] = f"parse error: {e!r}"
            print(f"[{i}/{len(companies)}] {company.name}: PARSE FAILED ({e!r})", flush=True)
            continue
        per_company[company.name] = len(found)
        jobs.extend(found)
        print(f"[{i}/{len(companies)}] {company.name}: {len(found)} jobs", flush=True)

    unique = dedupe(jobs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "jobs": [j.to_dict() for j in unique],
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))

    # Run summary (skills.md §7): fetched, kept, per-source errors.
    print(f"\nCompanies: {len(companies)} ok={len(per_company)} failed={len(errors)}")
    print(f"Jobs: fetched={len(jobs)} after_dedupe={len(unique)} -> {args.out}")
    print(f"Took {time.monotonic() - started:.0f}s")
    for name, err in errors.items():
        print(f"  error: {name}: {err}")
    # Fail the run only if nothing worked; a few dead boards are normal.
    return 1 if companies and not per_company else 0


if __name__ == "__main__":
    sys.exit(main())
