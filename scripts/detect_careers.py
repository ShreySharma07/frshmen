"""Find each company's careers page and recognise the hiring system behind it.

Phase A of docs/strategy/company-coverage.md. Many companies don't post on a shared job board
under their own name: their website's "Careers" link leads to Workday, SuccessFactors, an
embedded Greenhouse board under another slug, or their own pages. This reads the company's
website (homepage, then its careers page), and recognises the system from links, embeds and
redirects. A system we can read sets the company's `ats`/`slug`, so scripts/verify_companies.py
and the pipeline pick it up; one we can't read yet is recorded in `careers` for phase D.

Good citizen: robots.txt is checked for every host, requests are paced per host by HttpClient,
and at most a handful of pages are read per company.

Run: python scripts/detect_careers.py [--only NAME ...] [--all] [--limit N] [--report FILE]
By default it checks companies whose board isn't verified yet.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.robotparser
from collections import Counter
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402

from sources.http import USER_AGENT, FetchError, HttpClient  # noqa: E402

COMPANIES = ROOT / "config" / "companies.yaml"
YC_SOURCE = "https://raw.githubusercontent.com/yc-oss/api/main/companies/all.json"
MAX_PAGES = 6  # homepage + careers candidates per company

# --- Recognising systems -----------------------------------------------------------------------

Slug = Callable[[re.Match[str]], str]

# Systems we can read (an adapter in sources/), most specific first. Each pattern finds the
# board identifier in a link, iframe, script or redirect target.
SUPPORTED: list[tuple[str, re.Pattern[str], Slug]] = [
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)"), lambda m: m[1]),
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([A-Za-z0-9_-]+)"),
     lambda m: m[1]),
    ("lever", re.compile(r"jobs\.lever\.co/([A-Za-z0-9_.-]+)"), lambda m: m[1]),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)"), lambda m: m[1]),
    ("workable", re.compile(r"apply\.workable\.com/([A-Za-z0-9_-]+)"), lambda m: m[1]),
    ("smartrecruiters", re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9_-]+)"), lambda m: m[1]),
    ("workday", re.compile(r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)"),
     lambda m: f"{m[1]}/{m[2]}/{m[3]}"),
    ("oracle", re.compile(r"([a-z0-9-]+\.fa\.[a-z0-9-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[a-z]{2}(?:-[A-Z]{2})?/sites/([A-Za-z0-9_-]+)"),
     lambda m: f"{m[1]}/{m[2]}"),
    ("darwinbox", re.compile(r"\b([a-z0-9-]+)\.darwinbox\.in\b"), lambda m: m[1]),
    ("keka", re.compile(r"\b([a-z0-9-]+)\.keka\.com/careers"), lambda m: m[1]),
    ("zoho_recruit", re.compile(r"\b([a-z0-9-]+\.zohorecruit\.(?:in|com))\b"), lambda m: m[1]),
]

# Systems we recognise but can't read yet: counted for phase D (new adapters).
UNSUPPORTED: list[tuple[str, re.Pattern[str]]] = [
    ("successfactors", re.compile(r"successfactors\.(?:com|eu)|jobs\.sap\.com|rmkcdn\.successfactors")),
    ("phenom", re.compile(r"phenompeople\.com|phenom\.com/(?:cdn|widgets)")),
    ("icims", re.compile(r"\b[a-z0-9-]+\.icims\.com")),
    ("taleo", re.compile(r"\btaleo\.net")),
    ("eightfold", re.compile(r"\beightfold\.ai")),
    ("jobvite", re.compile(r"jobs\.jobvite\.com")),
    ("bamboohr", re.compile(r"\b[a-z0-9-]+\.bamboohr\.com/(?:careers|jobs)")),
    ("freshteam", re.compile(r"\b[a-z0-9-]+\.freshteam\.com")),
    ("recruitee", re.compile(r"\b[a-z0-9-]+\.recruitee\.com")),
    ("teamtailor", re.compile(r"\bteamtailor\.com")),
    ("personio", re.compile(r"jobs\.personio\.(?:de|com)")),
]

# Path segments that a board pattern can catch but that are never a company's board.
NOT_SLUGS = {"embed", "js", "v1", "api", "jobs", "job", "careers", "static", "assets", "en", "en-us", "search", "wday"}
# Google lists a job only if its page carries this, so most careers sites publish it.
JOB_POSTING = re.compile(r'"@type"\s*:\s*\[?\s*"JobPosting"')

CAREER_WORDS = re.compile(r"\b(careers?|jobs|join(?:\s+(?:us|our team|the team))?|we'?re hiring|hiring|"
                          r"work with us|open (?:roles|positions))\b", re.I)
CAREER_PATHS = ["/careers", "/jobs", "/careers/", "/company/careers", "/about/careers", "/join-us", "/join"]
ANCHOR = re.compile(r"<a\b[^>]*?href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)


@dataclass
class Found:
    system: str
    slug: str | None  # None for systems we can't read yet
    supported: bool
    url: str  # the page where it was seen


@dataclass
class Detection:
    website: str
    careers_url: str | None = None
    found: list[Found] = field(default_factory=list)
    pages: int = 0
    blocked: list[str] = field(default_factory=list)  # pages robots.txt told us not to read

    @property
    def best(self) -> Found | None:
        """The board this company most likely posts on: supported first, then the most-seen slug."""
        supported = [f for f in self.found if f.supported]
        if supported:
            counts = Counter((f.system, f.slug) for f in supported)
            (system, slug), _ = counts.most_common(1)[0]
            return next(f for f in supported if (f.system, f.slug) == (system, slug))
        return self.found[0] if self.found else None


def fingerprint(html: str, url: str) -> list[Found]:
    """Every hiring system named in a page's HTML or its own address, in the order found."""
    text = unescape(html) + "\n" + url
    out: list[Found] = []
    for system, pattern, slug_of in SUPPORTED:
        for m in pattern.finditer(text):
            slug = slug_of(m)
            if any(part.lower() in NOT_SLUGS for part in slug.split("/")):
                continue
            out.append(Found(system, slug, True, url))
    if JOB_POSTING.search(html):
        # A careers site publishing schema.org jobs: sources/careersite.py reads it by host.
        out.append(Found("careersite", urlparse(url).netloc, True, url))
    for system, pattern in UNSUPPORTED:
        if pattern.search(text):
            out.append(Found(system, None, False, url))
    return out


def career_links(html: str, base_url: str) -> list[str]:
    """Links that look like the careers page: by their text or address, same site or a hiring system."""
    site = registrable(urlparse(base_url).netloc)
    links: list[str] = []
    for href, label in ANCHOR.findall(html):
        label = re.sub(r"<[^>]+>", " ", label)
        if not (CAREER_WORDS.search(label) or CAREER_WORDS.search(href)):
            continue
        absolute = urljoin(base_url, unescape(href.strip()))
        host = urlparse(absolute).netloc
        if not host or urlparse(absolute).scheme not in ("http", "https"):
            continue
        if registrable(host) == site or any(p.search(absolute) for _, p, _ in SUPPORTED) \
                or any(p.search(absolute) for _, p in UNSUPPORTED):
            links.append(absolute)
    return list(dict.fromkeys(links))


def registrable(host: str) -> str:
    """'careers.acme.co.in' -> 'acme.co.in': enough to tell our site from someone else's."""
    parts = host.lower().split(":")[0].split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "ac", "gov"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


# --- Reading the web politely ------------------------------------------------------------------

class Robots:
    """robots.txt per host. A missing file allows everything; an unreadable one is treated as missing."""

    def __init__(self, http: HttpClient):
        self.http = http
        self.parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        key = f"{p.scheme}://{p.netloc}"
        if key not in self.parsers:
            parser = urllib.robotparser.RobotFileParser()
            try:
                text = self.http.get_text(f"{key}/robots.txt", accept="text/plain,*/*;q=0.5")
            except FetchError:
                text = None
            parser.parse((text or "").splitlines())
            self.parsers[key] = parser
        return self.parsers[key].can_fetch(USER_AGENT, url)


def detect(http: HttpClient, website: str, robots: Robots | None = None) -> Detection:
    """Read the homepage, then the most careers-looking pages, until a readable board turns up."""
    robots = robots or Robots(http)
    home = website if website.startswith("http") else f"https://{website}"
    result = Detection(website=home)
    queue = [home] + [urljoin(home, p) for p in CAREER_PATHS]
    seen: set[str] = set()
    dead: set[str] = set()  # hosts that never answered: don't wait on them again for each path
    while queue and result.pages < MAX_PAGES:
        url = queue.pop(0)
        if url in seen or urlparse(url).netloc in dead:
            continue
        seen.add(url)
        if not robots.allowed(url):
            result.blocked.append(url)
            continue
        try:
            page = http.get_page(url)
        except FetchError:
            dead.add(urlparse(url).netloc)
            continue
        result.pages += 1
        if page is None:
            continue
        final_url, html = page
        found = fingerprint(html, final_url)
        if found and url != home:
            result.careers_url = result.careers_url or final_url
        result.found += found
        if any(f.supported for f in found):
            result.careers_url = result.careers_url or final_url
            break
        # Links from this page that look like careers pages jump the queue.
        queue = [u for u in career_links(html, final_url) if u not in seen] + queue
    return result


# --- companies.yaml ----------------------------------------------------------------------------

def yc_websites(source: str = YC_SOURCE) -> dict[str, str]:
    """Company name -> website from the yc-oss dataset (all YC companies, hiring or not)."""
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(source, headers={"User-Agent": USER_AGENT}), timeout=60) as r:
            data = json.load(r)
    except Exception as e:  # noqa: BLE001 - the dataset is a convenience; hand-written websites still work
        print(f"yc-oss dataset unavailable ({e}); using websites on file only", file=sys.stderr)
        return {}
    return {norm(c["name"]): c["website"] for c in data if c.get("name") and c.get("website")}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def apply(company: dict[str, Any], d: Detection) -> dict[str, Any]:
    """The company entry after detection. A readable board resets verification so it is re-probed."""
    updated = dict(company, website=urlparse(d.website).netloc or d.website)
    best = d.best
    if best is None:
        updated["careers"] = f"not found ({d.pages} pages read" + (f", {len(d.blocked)} disallowed" if d.blocked else "") + ")"
        return updated
    if best.supported:
        if (best.system, best.slug) != (company.get("ats"), str(company.get("slug"))):
            updated.update(ats=best.system, slug=best.slug)
            for k in ("verified", "jobs", "ai_jobs", "checked"):
                updated.pop(k, None)  # not yet probed under the new board
        updated["careers"] = f"{best.system}: {best.url}"
    else:
        updated["careers"] = f"{best.system} (no adapter yet): {best.url}"
    return updated


def main() -> int:
    from verify_companies import rewrite_yaml  # same one-line-per-company format

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", help="check only these company names")
    parser.add_argument("--all", action="store_true", help="check every company, even verified ones and ones read before")
    parser.add_argument("--limit", type=int, default=0, help="stop after N companies")
    parser.add_argument("--report", type=Path, help="write a Markdown summary here")
    parser.add_argument("--minutes", type=float, default=0,
                        help="stop starting new companies after this long; the rest wait for the next run")
    args = parser.parse_args()

    text = COMPANIES.read_text()
    companies = yaml.safe_load(text)["companies"]
    if args.only:
        todo = [c for c in companies if c["name"] in set(args.only)]
    elif args.all:
        todo = companies
    else:
        # Unverified, and not read by an earlier run: a run cut short by --minutes resumes here.
        todo = [c for c in companies if not c.get("verified") and not c.get("careers")]
    if args.limit:
        todo = todo[: args.limit]

    yc = yc_websites() if any(not c.get("website") and c["category"] == "yc" for c in todo) else {}
    http = HttpClient(retries=1, timeout=15)
    robots = Robots(http)
    results: dict[str, dict[str, Any]] = {}
    rows: list[str] = []

    def save() -> None:
        # Saved every few companies, so a run cut off by the job's time limit keeps its work.
        COMPANIES.write_text(rewrite_yaml(text, results))
        summary = Counter(r["careers"].split(":")[0].split(" (")[0] for r in results.values())
        lines = ["# Careers-system detection", "",
                 f"{len(results)} companies read. Systems found: "
                 + ", ".join(f"{k} {v}" for k, v in summary.most_common()) + ".", "",
                 "| Company | Website | Careers system | Board changed |", "|---|---|---|---|", *rows]
        if args.report:
            args.report.write_text("\n".join(lines) + "\n")
        print("\n" + lines[2], flush=True)

    deadline = time.monotonic() + args.minutes * 60 if args.minutes else None
    for i, company in enumerate(todo, 1):
        if deadline and time.monotonic() > deadline:
            print(f"Time budget reached after {i - 1}/{len(todo)} companies; the rest wait for the next run.")
            break
        website = company.get("website") or yc.get(norm(company["name"]))
        if not website:
            print(f"[{i}/{len(todo)}] {company['name']}: no website on file, skipped", flush=True)
            rows.append(f"| {company['name']} | | no website on file | |")
            continue
        d = detect(http, website, robots)
        updated = apply(company, d)
        results[company["name"]] = updated
        changed = (updated.get("ats"), str(updated.get("slug"))) != (company.get("ats"), str(company.get("slug")))
        print(f"[{i}/{len(todo)}] {company['name']}: {updated['careers']}{'  (board changed)' if changed else ''}", flush=True)
        rows.append(f"| {company['name']} | {updated['website']} | {updated['careers']} | {'yes' if changed else ''} |")
        if i % 10 == 0:
            save()
    save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
