"""Find new companies to fetch, verify their boards, and add a batch to config/companies.yaml.

Two sources (see docs/decisions.md):
- yc-oss: hiring YC AI startups that now pass scripts/import_yc.py's filter (new batches,
  or older ones that have grown past the team-size bar).
- Hacker News "Who is hiring?": board links (Greenhouse, Lever, Ashby, Workable,
  SmartRecruiters, Workday) inside the last two monthly threads' posts.

Each candidate's board is probed live, and only boards with at least one open title that
names a target role (by the same title rules as extract/role.py) are kept. The run is stateless: rejects are simply found and
dropped again next time. Nothing is written until at least MIN_BATCH companies qualify,
so the weekly workflow opens one PR per 10-20 companies instead of a trickle.

Run: python scripts/discover_companies.py [--min N] [--max N] [--dry-run] [--pr-body FILE]
Exit 0 always on success; prints "ready=true|false" (also to $GITHUB_OUTPUT).
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # `sources`
sys.path.insert(0, str(ROOT / "scripts"))  # sibling scripts, imported the way the tests import them

import yaml  # noqa: E402

import import_yc  # noqa: E402
from verify_companies import AI_TITLE, find_board, format_line  # noqa: E402
from sources import hn  # noqa: E402
from sources.http import FetchError, HttpClient  # noqa: E402
from extract.profile import load_profile  # noqa: E402
from extract.role import match_role  # noqa: E402

COMPANIES = ROOT / "config" / "companies.yaml"
MIN_BATCH = 10
MAX_BATCH = 20
# Bounds one run's probing (each candidate is a few requests, paced per host).
MAX_CANDIDATES = 200
HN_THREADS = 2

# Board links as they appear in HN posts. Lever's EU host and Greenhouse's EU host use
# other APIs, so they're left out rather than mis-probed.
_BOARD_LINKS: list[tuple[str, re.Pattern[str]]] = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)")),
    ("lever", re.compile(r"(?<!eu\.)jobs\.lever\.co/([A-Za-z0-9_.-]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)")),
    ("workable", re.compile(r"apply\.workable\.com/([A-Za-z0-9_-]+)")),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)")),
    ("workday", re.compile(r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)")),
]
# Path segments that are part of the host's own UI, not a company's board.
_NOT_A_SLUG = {"embed", "j", "api", "jobs", "job", "v1", "en", "careers", "search", "login"}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def title_fits(title: str) -> bool:
    """Does a title alone name a target role? Families that need the description to
    confirm (Python backend, Android stack) count; plain "Software Engineer" doesn't,
    or every tech company would qualify."""
    m = match_role(title, "", load_profile())
    return m.is_target or m.family in {"backend", "mobile"}


def pretty_slug(slug: str) -> str:
    return re.sub(r"[-_.]+", " ", slug.split("/")[0]).strip().title()


def board_links(text: str) -> list[tuple[str, str]]:
    """(ats, slug) for every supported board linked in a post, in order of appearance."""
    text = html.unescape(text or "")
    found: list[tuple[int, str, str]] = []
    for ats, pattern in _BOARD_LINKS:
        for m in pattern.finditer(text):
            slug = "/".join(m.groups()) if ats == "workday" else m.group(1).rstrip(".")
            if ats != "workday" and slug.lower() in _NOT_A_SLUG:
                continue
            found.append((m.start(), ats, slug))
    return list(dict.fromkeys((ats, slug) for _, ats, slug in sorted(found)))


def hn_candidates(threads: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for thread in threads:
        for post in thread.get("children") or []:
            parts = hn.header_parts(post.get("text"))
            links = board_links(post.get("text") or "")
            if not parts or not links:
                continue
            ats, slug = links[0]  # a post's first board link is its own; later ones are rare asides
            name = hn.company_name(parts)[:80]
            # Some headers lead with a place or "Remote"; trust the name only if the board agrees.
            if norm(name) not in norm(slug) and norm(slug) not in norm(name):
                name = pretty_slug(slug)
            out.append({"name": name, "category": "hn", "hq": "global",
                        "ats": ats, "slug": slug})
    return out


def yc_candidates(dataset: list[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in e.items() if k != "verified"} for e in import_yc.new_entries(dataset, existing)]


def dedupe(candidates: Iterable[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop candidates already on file, by name or by board, and repeats within the batch."""
    names = {norm(c["name"]) for c in existing}
    boards = {(c["ats"], str(c["slug"]).lower()) for c in existing}
    out = []
    for c in candidates:
        key = (c["ats"], str(c["slug"]).lower())
        if not norm(c["name"]) or norm(c["name"]) in names or key in boards:
            continue
        names.add(norm(c["name"]))
        boards.add(key)
        out.append(c)
    return out


def qualify(http: HttpClient, candidate: dict[str, Any], today: str) -> dict[str, Any] | None:
    """The candidate as a verified companies.yaml entry, or None if its board has no target roles."""
    try:
        board = find_board(http.get_json, candidate, http)
    except FetchError as e:
        print(f"  {candidate['name']}: no answer ({e})", file=sys.stderr, flush=True)
        return None
    if board is None or not any(title_fits(t) for t in board.titles):
        return None
    return dict(candidate, ats=board.ats, slug=board.slug, verified=True, jobs=len(board.titles),
                ai_jobs=sum(bool(AI_TITLE.search(t)) for t in board.titles), checked=today)


def pick(found: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    # Most AI/ML titles first: those boards are the likeliest to carry target roles.
    return sorted(found, key=lambda c: (-c["ai_jobs"], -c["jobs"], c["name"].lower()))[:limit]


def append_section(text: str, entries: list[dict[str, Any]], today: str) -> str:
    lines = [f"\n  # --- Auto-discovered on {today} (scripts/discover_companies.py) ---\n"]
    lines += [format_line("  ", e) for e in entries]
    return text.rstrip("\n") + "\n" + "".join(lines)


def pr_body(entries: list[dict[str, Any]]) -> str:
    rows = [f"| {e['name']} | {e['category']} | {e['ats']} | `{e['slug']}` | {e['jobs']} | {e['ai_jobs']} |"
            for e in entries]
    return "\n".join([
        f"Adds {len(entries)} companies found by `scripts/discover_companies.py`. Each board was probed "
        "live and has at least one open title that could be a target role.",
        "",
        "Check that each board belongs to the company named (a slug can hit a namesake), then merge. "
        "Delete any line you don't want.",
        "",
        "| Company | Source | ATS | Slug | Open jobs | AI/ML titles |",
        "|---|---|---|---|---:|---:|",
        *rows,
        "",
    ])


def set_output(ready: bool) -> None:
    print(f"ready={'true' if ready else 'false'}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"ready={'true' if ready else 'false'}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min", type=int, default=MIN_BATCH, help="write nothing below this many")
    parser.add_argument("--max", type=int, default=MAX_BATCH, help="add at most this many")
    parser.add_argument("--dry-run", action="store_true", help="probe and report, write nothing")
    parser.add_argument("--pr-body", type=Path, help="also write a PR description here")
    args = parser.parse_args()

    today = date.today().isoformat()
    text = COMPANIES.read_text()
    existing = yaml.safe_load(text)["companies"]
    http = HttpClient()

    candidates: list[dict[str, Any]] = []
    try:
        candidates += hn_candidates(hn.recent_threads(http, HN_THREADS))
    except FetchError as e:
        print(f"HN unavailable: {e}", file=sys.stderr)
    try:
        candidates += yc_candidates(import_yc.load_source(import_yc.SOURCE), existing)
    except OSError as e:
        print(f"yc-oss unavailable: {e}", file=sys.stderr)
    candidates = dedupe(candidates, existing)[:MAX_CANDIDATES]
    print(f"{len(candidates)} new candidates to probe", flush=True)

    found = []
    for i, c in enumerate(candidates, 1):
        entry = qualify(http, c, today)
        print(f"[{i}/{len(candidates)}] {c['name']} ({c['ats']}/{c['slug']}): "
              f"{'%d jobs, %d AI/ML' % (entry['jobs'], entry['ai_jobs']) if entry else 'skipped'}", flush=True)
        if entry:
            found.append(entry)

    batch = pick(found, args.max)
    print(f"\n{len(found)} qualify; batch of {len(batch)} (needs {args.min})")
    ready = len(batch) >= args.min
    if ready and not args.dry_run:
        COMPANIES.write_text(append_section(text, batch, today))
        if args.pr_body:
            args.pr_body.write_text(pr_body(batch))
    set_output(ready and not args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
