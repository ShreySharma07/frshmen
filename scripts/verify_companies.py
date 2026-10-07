"""Check which ATS board each company in config/companies.yaml actually uses.

For each company, try the guessed (ats, slug) first, then every other supported ATS
with a few slug variants derived from the name. The first board that answers wins.
Results are written back into companies.yaml (one line per company, comments kept)
and summarised in docs/company_check.md so Shrey can prune.

Run: python scripts/verify_companies.py [--only NAME ...]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `sources` imports when run as a plain script

import yaml  # noqa: E402

from sources import ADAPTERS  # noqa: E402
from sources.http import FetchError, HttpClient  # noqa: E402

COMPANIES = ROOT / "config" / "companies.yaml"
REPORT = ROOT / "docs" / "company_check.md"

ATS_ORDER = ["greenhouse", "lever", "ashby", "workable", "smartrecruiters"]
# Probed only when it is the company's guessed ATS: Workable throttles hard and
# few of our companies use it, so trying it for everyone mostly bought 429s.
GUESS_ONLY_ATS = {"workable"}
# Careers-site systems whose identifier can't be guessed from a name (Workday needs
# tenant/wdN/site, Keka a portal id...): probed only with the exact slug on file.
EXACT_SLUG_ATS = {"workday", "darwinbox", "keka", "zoho_recruit", "amazon", "eightfold", "hn"}
KEY_ORDER = ["name", "category", "hq", "ats", "slug", "india_only", "verified", "jobs", "ai_jobs", "checked"]
# Boards found missing or empty aren't re-probed for this long, so a PR run only probes new entries.
RECHECK_DAYS = 7

# Rough title filter, only to help pruning; real classification lives in extract/.
AI_TITLE = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|llm|genai|gen ai|deep learning|"
    r"data scien\w*|applied scien\w*|research (engineer|scientist)|nlp|computer vision|mlops|"
    r"inference|perception)\b",
    re.I,
)


@dataclass
class Board:
    ats: str
    slug: str
    titles: list[str]
    board_name: str | None = None
    sample_url: str | None = None


GetJson = Callable[[str], Any]


def probe_greenhouse(get: GetJson, slug: str) -> Board | None:
    data = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if not isinstance(data, dict) or "jobs" not in data:
        return None
    meta = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}") or {}
    jobs = data["jobs"]
    return Board("greenhouse", slug, [j.get("title", "") for j in jobs], meta.get("name"),
                 jobs[0].get("absolute_url") if jobs else None)


def probe_lever(get: GetJson, slug: str) -> Board | None:
    data = get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not isinstance(data, list):
        return None
    return Board("lever", slug, [j.get("text", "") for j in data], None,
                 data[0].get("hostedUrl") if data else None)


def probe_ashby(get: GetJson, slug: str) -> Board | None:
    data = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        return None
    jobs = data["jobs"]
    return Board("ashby", slug, [j.get("title", "") for j in jobs], None,
                 jobs[0].get("jobUrl") if jobs else None)


def probe_workable(get: GetJson, slug: str) -> Board | None:
    data = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    # Many companies keep a dormant Workable account with no jobs while hiring
    # elsewhere; an empty one says nothing, so treat it as not found.
    if not isinstance(data, dict) or not data.get("jobs"):
        return None
    jobs = data["jobs"]
    return Board("workable", slug, [j.get("title", "") for j in jobs], data.get("name"),
                 jobs[0].get("url") if jobs else None)


def probe_smartrecruiters(get: GetJson, slug: str) -> Board | None:
    data = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings")
    # SmartRecruiters answers 200 with zero results for unknown companies, so an
    # empty board is indistinguishable from a wrong slug; treat it as not found.
    if not isinstance(data, dict) or not data.get("content"):
        return None
    jobs = data["content"]
    company = (jobs[0].get("company") or {}).get("name")
    return Board("smartrecruiters", slug, [j.get("name", "") for j in jobs], company,
                 f"https://jobs.smartrecruiters.com/{slug}/{jobs[0].get('id')}")


PROBES: dict[str, Callable[[GetJson, str], Board | None]] = {
    "greenhouse": probe_greenhouse,
    "lever": probe_lever,
    "ashby": probe_ashby,
    "workable": probe_workable,
    "smartrecruiters": probe_smartrecruiters,
}


def slug_variants(company: dict[str, Any]) -> list[str]:
    # "Anysphere (Cursor)" -> try both "anysphere" and "cursor".
    names = [re.sub(r"\(.*?\)", "", company["name"])] + re.findall(r"\((.*?)\)", company["name"])
    variants = [str(company["slug"])]
    for n in (n.strip().lower() for n in names):
        variants += [re.sub(r"[^a-z0-9]", "", n), re.sub(r"[^a-z0-9]+", "-", n).strip("-")]
    return list(dict.fromkeys(v for v in variants if v))


def probe_exact(http: HttpClient | None, ats: str, slug: str) -> Board | None:
    try:
        titles = ADAPTERS[ats].list_titles(http, slug) if http is not None else None
    except FetchError as e:
        # A 403 is the site refusing our bot (Darwinbox does this to GitHub's runners), not a
        # flaky answer: record it as checked so it is retried weekly instead of failing every run.
        if "HTTP 403" in str(e):
            print(f"  {slug}: refused (HTTP 403); counted as not available", file=sys.stderr, flush=True)
            return None
        raise
    return None if titles is None else Board(ats, slug, titles)


def find_board(get: GetJson, company: dict[str, Any], http: HttpClient | None = None) -> Board | None:
    """Return the first board with open jobs; an empty board only if nothing better exists.

    An empty board on the guessed ATS is often a stale account, so keep looking.
    """
    guessed = company["ats"]
    if guessed in EXACT_SLUG_ATS:
        return probe_exact(http, guessed, str(company["slug"]))
    attempts = [(guessed, company["slug"])]
    hosts = [guessed] + [a for a in ATS_ORDER if a != guessed and a not in GUESS_ONLY_ATS]
    # Slug-major order alternates hosts, so one host's per-host delay overlaps the others' requests.
    for slug in slug_variants(company):
        attempts += [(ats, slug) for ats in hosts]
    empty: Board | None = None
    errors: list[str] = []
    for ats, slug in dict.fromkeys(attempts):
        try:
            board = PROBES[ats](get, slug)
        except FetchError as e:
            # One throttled host shouldn't stop us finding the board on another.
            errors.append(str(e))
            continue
        if board is None:
            continue
        if board.titles:
            return board
        empty = empty or board
    if empty is None and errors:
        # Can't claim "not found" when some probes never got an answer.
        raise FetchError("; ".join(dict.fromkeys(errors)))
    return empty


def needs_check(company: dict[str, Any], today: date | None = None) -> bool:
    if company.get("verified") is True and company.get("jobs"):
        return False
    # Missing or empty boards are rechecked weekly: the company may have moved ATS or started hiring.
    checked = company.get("checked")
    if checked:
        today = today or date.today()
        return (today - date.fromisoformat(str(checked))).days >= RECHECK_DAYS
    return True


def format_line(indent: str, company: dict[str, Any]) -> str:
    ordered = {k: company[k] for k in KEY_ORDER if k in company}
    body = yaml.safe_dump(ordered, default_flow_style=True, sort_keys=False, width=1000).strip()
    return f"{indent}- {body}\n"


def rewrite_yaml(text: str, results: dict[str, dict[str, Any]]) -> str:
    """Replace only the company lines we checked, so comments and grouping survive."""
    out = []
    for line in text.splitlines(keepends=True):
        m = re.match(r"^(\s*)- (\{.*\})\s*$", line)
        if m:
            entry = yaml.safe_load(m.group(2))
            if entry.get("name") in results:
                line = format_line(m.group(1), results[entry["name"]])
        out.append(line)
    return "".join(out)


def write_report(companies: list[dict[str, Any]], boards: dict[str, Board | None]) -> None:
    """Summarise every company's current state; board name/sample only for ones checked this run."""
    found = [c for c in companies if c.get("verified")]
    lines = [
        "# Company board check",
        "",
        f"Generated by `scripts/verify_companies.py`. {len(found)}/{len(companies)} companies have a public board "
        "on a supported ATS.",
        "",
        "`AI/ML` counts titles matching a rough keyword filter; it is a pruning hint, not the real classifier. "
        "Where the board name or sample link doesn't match the company, the slug hit the wrong company: fix or delete it. "
        "Name/sample is shown only for companies checked in the latest run.",
        "",
        "| Company | Category | ATS | Slug | Open jobs | AI/ML titles | Board name / sample |",
        "|---|---|---|---|---:|---:|---|",
    ]

    def status(c: dict[str, Any]) -> int:
        return 0 if c.get("verified") else 1 if c.get("verified") is False else 2

    for c in sorted(companies, key=lambda c: (status(c), c["category"], c["name"].lower())):
        if c.get("verified") is False:
            lines.append(f"| {c['name']} | {c['category']} | not found | | | | |")
        elif "verified" not in c:
            lines.append(f"| {c['name']} | {c['category']} | not checked yet | | | | |")
        else:
            b = boards.get(c["name"])
            hint = (b.board_name or (f"[sample]({b.sample_url})" if b.sample_url else "")) if b else ""
            lines.append(f"| {c['name']} | {c['category']} | {c['ats']} | `{c['slug']}` | {c['jobs']} | {c['ai_jobs']} | {hint} |")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", help="check only these company names")
    parser.add_argument("--all", action="store_true", help="recheck every company, not just unverified/empty ones")
    args = parser.parse_args()

    text = COMPANIES.read_text()
    companies = yaml.safe_load(text)["companies"]
    all_companies = companies
    if args.only:
        companies = [c for c in companies if c["name"] in set(args.only)]
    elif not args.all:
        companies = [c for c in companies if needs_check(c)]

    http = HttpClient()  # no cache: we want a fresh answer about each board
    boards: dict[str, Board | None] = {}
    results: dict[str, dict[str, Any]] = {}
    for i, company in enumerate(companies, 1):
        try:
            board = find_board(http.get_json, company, http)
        except FetchError as e:
            print(f"[{i}/{len(companies)}] {company['name']}: gave up after retries, left unchanged ({e})", file=sys.stderr, flush=True)
            continue
        updated = dict(company, checked=date.today().isoformat())
        if board:
            updated.update(ats=board.ats, slug=board.slug, verified=True, jobs=len(board.titles),
                           ai_jobs=sum(bool(AI_TITLE.search(t)) for t in board.titles))
        else:
            updated.update(verified=False)
            for k in ("jobs", "ai_jobs"):
                updated.pop(k, None)
        results[company["name"]] = updated
        boards[company["name"]] = board
        status = f"{board.ats}/{board.slug} ({len(board.titles)} jobs)" if board else "not found"
        print(f"[{i}/{len(companies)}] {company['name']}: {status}", flush=True)

    if companies and not boards:
        print("Nothing checked (network blocked?). Files left unchanged.", file=sys.stderr)
        return 1
    COMPANIES.write_text(rewrite_yaml(text, results))
    write_report([results.get(c["name"], c) for c in all_companies], boards)
    print(f"\n{sum(1 for b in boards.values() if b)}/{len(boards)} found this run "
          f"({len(companies) - len(boards)} gave up). Report: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
