"""Check which ATS board each company in config/companies.yaml actually uses.

For each company, try the guessed (ats, slug) first, then every other supported ATS
with a few slug variants derived from the name. The first board that answers wins.
Results are written back into companies.yaml (one line per company, comments kept)
and summarised in docs/company_check.md so Shrey can prune.

Run: python scripts/verify_companies.py [--only NAME ...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "config" / "companies.yaml"
REPORT = ROOT / "docs" / "company_check.md"

USER_AGENT = "frshmen-jobboard/0.1 (personal job board; +https://github.com/ShreySharma07/frshmen)"
MIN_SECONDS_PER_HOST = 1.0
ATS_ORDER = ["greenhouse", "lever", "ashby", "workable", "smartrecruiters"]
KEY_ORDER = ["name", "category", "hq", "ats", "slug", "verified", "jobs", "ai_jobs"]

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


@dataclass
class Fetcher:
    """GET JSON politely: identify ourselves and space out requests per host."""

    last_hit: dict[str, float] = field(default_factory=dict)

    def get_json(self, url: str) -> Any | None:
        host = urlparse(url).netloc
        wait = MIN_SECONDS_PER_HOST - (time.monotonic() - self.last_hit.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        self.last_hit[host] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 410):
                return None
            raise
        except json.JSONDecodeError:
            return None


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
    if not isinstance(data, dict) or "jobs" not in data:
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
    base = re.sub(r"\(.*?\)", "", company["name"]).strip().lower()
    variants = [str(company["slug"]), re.sub(r"[^a-z0-9]", "", base), re.sub(r"[^a-z0-9]+", "-", base).strip("-")]
    return list(dict.fromkeys(v for v in variants if v))


def find_board(get: GetJson, company: dict[str, Any]) -> Board | None:
    guessed = company["ats"]
    attempts = [(guessed, company["slug"])]
    for ats in [guessed] + [a for a in ATS_ORDER if a != guessed]:
        attempts += [(ats, s) for s in slug_variants(company)]
    for ats, slug in dict.fromkeys(attempts):
        board = PROBES[ats](get, slug)
        if board is not None:
            return board
    return None


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


def write_report(rows: list[tuple[dict[str, Any], Board | None]]) -> None:
    found = [r for r in rows if r[1]]
    lines = [
        "# Company board check",
        "",
        f"Generated by `scripts/verify_companies.py`. {len(found)}/{len(rows)} companies have a public board "
        "on a supported ATS.",
        "",
        "`AI/ML` counts titles matching a rough keyword filter; it is a pruning hint, not the real classifier. "
        "Where the board name or sample link doesn't match the company, the slug hit the wrong company: fix or delete it.",
        "",
        "| Company | Category | ATS | Slug | Open jobs | AI/ML titles | Board name / sample |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for c, b in sorted(rows, key=lambda r: (r[1] is None, r[0]["category"], r[0]["name"].lower())):
        if b is None:
            lines.append(f"| {c['name']} | {c['category']} | not found | | | | |")
            continue
        ai = sum(bool(AI_TITLE.search(t)) for t in b.titles)
        hint = b.board_name or (f"[sample]({b.sample_url})" if b.sample_url else "")
        lines.append(f"| {c['name']} | {c['category']} | {b.ats} | `{b.slug}` | {len(b.titles)} | {ai} | {hint} |")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", help="check only these company names")
    args = parser.parse_args()

    text = COMPANIES.read_text()
    companies = yaml.safe_load(text)["companies"]
    if args.only:
        companies = [c for c in companies if c["name"] in set(args.only)]

    fetcher = Fetcher()
    rows: list[tuple[dict[str, Any], Board | None]] = []
    results: dict[str, dict[str, Any]] = {}
    for i, company in enumerate(companies, 1):
        try:
            board = find_board(fetcher.get_json, company)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"[{i}/{len(companies)}] {company['name']}: network error, left unchanged ({e})", file=sys.stderr)
            continue
        updated = dict(company)
        if board:
            updated.update(ats=board.ats, slug=board.slug, verified=True, jobs=len(board.titles),
                           ai_jobs=sum(bool(AI_TITLE.search(t)) for t in board.titles))
        else:
            updated.update(verified=False)
            for k in ("jobs", "ai_jobs"):
                updated.pop(k, None)
        results[company["name"]] = updated
        rows.append((company, board))
        status = f"{board.ats}/{board.slug} ({len(board.titles)} jobs)" if board else "not found"
        print(f"[{i}/{len(companies)}] {company['name']}: {status}")

    if not rows:
        print("Nothing checked (network blocked?). Files left unchanged.", file=sys.stderr)
        return 1
    COMPANIES.write_text(rewrite_yaml(text, results))
    write_report(rows)
    print(f"\n{sum(1 for _, b in rows if b)}/{len(rows)} found. Report: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
