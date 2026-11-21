"""Fetch every verified company's board and write classified jobs to data/jobs.json.

fetch -> normalize -> dedupe -> classify (fresher / maybe / experienced, with
evidence); scripts/publish_pg.py stores the result. One broken board never stops the others.

Run: python scripts/fetch_jobs.py [--limit N] [--company NAME ...] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `sources` imports when run as a plain script

import yaml  # noqa: E402

from extract.classify import classify  # noqa: E402
from extract.eligibility import check_eligibility  # noqa: E402
from extract.location import REMOTE_UNSPECIFIED, extract_location  # noqa: E402
from extract.profile import load_profile  # noqa: E402
from extract.category import job_category  # noqa: E402
from extract.role import match_role  # noqa: E402
from extract.skills import skills_in  # noqa: E402
from extract.stored_text import compact  # noqa: E402
from extract.visa import extract_visa  # noqa: E402
from sources import ADAPTERS, manual  # noqa: E402
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


def pick(companies: list[Company], names: list[str] | None = None, limit: int | None = None,
         skip_global: bool = False) -> list[Company]:
    """The boards this run reads. skip_global leaves out the big global (india_only) boards, which are
    read once a day: they list thousands of slow-changing jobs, the startups' boards change by the hour.
    A board left out is missing from boards_ok too, so publish_pg.py leaves its jobs untouched."""
    if names:
        companies = [c for c in companies if c.name in set(names)]
    if skip_global:
        # Job boards refresh daily too (sources/himalayas.py), so they ride the same daily run.
        companies = [c for c in companies if not c.india_only and not is_daily(c)]
    return companies[:limit] if limit else companies


def is_board(source: str) -> bool:
    """A job board lists many companies' jobs (config/boards.yaml), unlike a company's own ATS."""
    return getattr(ADAPTERS.get(source), "BOARD", False)


def is_daily(company: Company) -> bool:
    return getattr(ADAPTERS.get(company.ats), "DAILY", False)


# Legal-form words that differ between a board's spelling and ours ("Acme, Inc." vs "Acme").
_LEGAL_FORM = re.compile(r"\b(?:inc|llc|ltd|limited|gmbh|corp|corporation|co|plc|pvt|private|sa|sarl|bv|ag)\b")


def company_key(name: str) -> str:
    """A company name reduced for matching across sources: "Acme AI, Inc." -> "acmeai"."""
    return re.sub(r"[^a-z0-9]", "", _LEGAL_FORM.sub("", name.lower()))


def drop_covered(jobs: list[Job], companies: list[Company]) -> tuple[list[Job], int]:
    """Board jobs from companies we already read directly are dropped: their own board is the
    better copy (fresher, complete, closes on time). Decision 2026-11-19, option C."""
    direct = {company_key(c.name) for c in companies if not is_board(c.ats)}
    kept = [j for j in jobs if not (is_board(j.source) and company_key(j.company) in direct)]
    return kept, len(jobs) - len(kept)


def open_jobs(dsn: str, prefix: str) -> list[tuple[str, str]]:
    """(id, company) of the jobs stored open under one board."""
    import psycopg  # only the full run with a database needs it

    # The name lives in companies (db/postgres/0001_schema.sql); jobs only has company_id.
    with psycopg.connect(dsn) as conn:
        return conn.execute("SELECT j.id, c.name FROM jobs j JOIN companies c ON c.id = j.company_id "
                            "WHERE j.status = 'open' AND starts_with(j.id, %s)", (prefix,)).fetchall()


def keep_still_open(http: HttpClient, boards: list[Company], fetched: set[str], covered: set[str], dsn: str | None,
                    stored: Callable[[str, str], list[tuple[str, str]]] = open_jobs) -> tuple[list[str], set[str]]:
    """For boards whose feed is a window, not the full list (Jobicy: last 7 days): stored open jobs
    missing from today's feed that the board confirms are still active. Returns (ids to keep open,
    boards that couldn't be checked). An unchecked board must not close anything: leave it out of
    boards_ok. `covered`: company keys read directly; their board copies are let go."""
    keep: list[str] = []
    unchecked: set[str] = set()
    for board in boards:
        adapter = ADAPTERS[board.ats]
        if not hasattr(adapter, "still_open"):
            continue
        if not dsn:
            unchecked.add(board.name)
            continue
        prefix = f"{board.ats}:{board.slug}:"
        try:
            missing = [jid for jid, company in stored(dsn, prefix)
                       if jid not in fetched and company_key(company) not in covered]
            active = adapter.still_open(http, [jid[len(prefix):] for jid in missing])
        except Exception as e:  # noqa: BLE001 - the database or the board: this board closes nothing,
            # the other boards still publish (a crash here once stopped every daily run)
            print(f"{board.name}: open jobs not checked ({type(e).__name__}: {e})"[:300], flush=True)
            unchecked.add(board.name)
            continue
        keep += [prefix + ext for ext in sorted(active)]
    return keep, unchecked


def board_leads(records: list[dict], path: Path = COMPANIES) -> list[dict]:
    """Companies seen on a job board with a target-role job, and not in our list at all: leads to
    add and read directly (the discovery half of option C)."""
    listed = {company_key(c["name"]) for c in yaml.safe_load(path.read_text())["companies"]}
    counts = Counter((r["source"], r["company"]) for r in records
                     if r["role_match"] and is_board(r["source"]) and company_key(r["company"]) not in listed)
    return [{"source": s, "company": c, "target_jobs": n} for (s, c), n in counts.most_common()]


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
    parser.add_argument("--skip-global", action="store_true",
                        help="leave out the big global boards (india_only); they are read once a day (docs/decisions.md)")
    args = parser.parse_args()

    companies = pick(load_companies(), args.company, args.limit, args.skip_global)

    http = HttpClient(cache_dir=None if args.no_cache else CACHE_DIR)
    started = time.monotonic()
    jobs: list[Job] = []
    errors: dict[str, str] = {}
    per_company: dict[str, int] = {}
    screened: list[int] = []  # jobs the India screen dropped, one entry per india_only board

    def fetch_one(company: Company) -> tuple[Company, list[Job] | None, str | None]:
        try:
            found = ADAPTERS[company.ats].fetch(http, company)
        except FetchError as e:
            return company, None, str(e)
        except (KeyError, TypeError, ValueError) as e:
            # The ATS changed its payload shape: report it, keep going.
            return company, None, f"parse error: {e!r}"
        if company.india_only:
            kept = [j for j in found if in_india_or_remote(j)]
            screened.append(len(found) - len(kept))  # list.append is safe across the pool's threads
            found = kept
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

    # Jobs added by hand in /admin, after the boards so a board's own copy of the same role wins
    # the dedupe. Full runs only (a smoke run names companies); a failure skips them and their
    # board entries, so nothing of theirs is closed by mistake.
    manual_boards: list[dict[str, str]] = []
    if os.environ.get("SUPABASE_DB_URL") and not (args.company or args.limit):
        try:
            found, manual_boards = manual.load(os.environ["SUPABASE_DB_URL"])
            jobs.extend(found)
            print(f"manual: {len(found)} jobs added by hand", flush=True)
        except Exception as e:  # noqa: BLE001 - the boards' jobs still publish
            errors["manual jobs"] = f"{type(e).__name__}: {e}"[:300]

    # Every listed company counts as covered, even if its board failed this run: a board copy shown
    # for one run would only be closed again on the next.
    listed = load_companies()
    fetched_ids = {j.id for j in jobs}
    jobs, covered = drop_covered(jobs, listed)
    keep_open, unchecked = keep_still_open(
        http, [c for c in companies if c.name in per_company], fetched_ids,
        {company_key(c.name) for c in listed if not is_board(c.ats)}, os.environ.get("SUPABASE_DB_URL"))
    for name in unchecked:
        errors[name] = "open jobs not checked against the board (no database or status check failed); none closed"
    unique = dedupe(jobs)
    profile = load_profile()
    records = []
    for j in unique:
        record = {
            **j.to_dict(),
            **classify(j.title, j.description_text, set(profile.exact_batch), set(profile.soft_batch)).to_dict(),
            **match_role(j.title, j.description_text, profile).to_dict(),
            **location_fields(j, profile.hide_onsite_only_in or frozenset({"bengaluru", "hyderabad"})),
        }
        record["category"] = job_category(j.title, record["role_family"])
        record["skills"] = skills_in(j.description_text)
        # Extractors have read the full text; only the sections a candidate needs are stored
        # (extract/stored_text.py). content_hash stays that of the full text.
        record["description_text"] = compact(j.description_text, record["evidence"])
        records.append(record)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        # Boards that answered: publish_pg.py only closes missing jobs from these.
        "boards_ok": [{"source": c.ats, "company_slug": c.slug} for c in companies
                      if c.name in per_company and c.name not in unchecked] + manual_boards,
        # Open jobs a board's window no longer lists but the board says are active (sources/jobicy.py).
        "keep_open": keep_open,
        "errors": errors,
        "board_leads": board_leads(records),
        "jobs": records,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))

    # Run summary (skills.md §7): fetched, kept, per-source errors.
    print(f"\nCompanies: {len(companies)} ok={len(per_company)} failed={len(errors)}")
    print(f"Jobs: fetched={len(jobs) + covered} after_dedupe={len(unique)} -> {args.out}")
    print(f"Job boards: dropped {covered} jobs from companies read directly; "
          f"{len(payload['board_leads'])} new companies with target-role jobs (board_leads)")
    # How much the India screen hides today: the size of "every country" for these boards
    # (docs/strategy/worldwide-coverage.md, phase 0).
    print(f"India screen: dropped {sum(screened)} jobs on {len(screened)} india_only boards")
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
