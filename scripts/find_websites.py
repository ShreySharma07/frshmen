"""Find the website of each working company that has none, so the job list can show its logo.

docs/decisions.md, 2026-11-04: only 57 of 433 working companies had a `website`. For each, a few
likely domains are tried (sarvam.ai, sarvam.com, <slug>.com ...), one homepage request each, and a
domain is kept only when that page's title names the company: a wrong logo is worse than the
tinted letter the site falls back to. robots.txt is honoured. Run by
.github/workflows/find-websites.yml, which commits the result to the PR branch.

Run: python scripts/find_websites.py [--limit N]
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from sources.http import USER_AGENT, FetchError, HttpClient  # noqa: E402
from verify_companies import COMPANIES, rewrite_yaml  # noqa: E402

# Words that don't tell companies apart, dropped before comparing a name with a page title.
_FILLER = re.compile(r"\b(inc|llc|ltd|limited|corp|corporation|technologies|technology|labs?|ai|hq|the|co)\b")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_SITE_NAME = re.compile(r"<meta[^>]+property=[\"']og:site_name[\"'][^>]+content=[\"']([^\"']+)", re.I)


def core(name: str) -> str:
    """'Sarvam AI' -> 'sarvam', 'Anysphere (Cursor)' -> 'anysphere': the part a title must contain."""
    name = re.sub(r"\(.*?\)", " ", name.lower())
    name = _FILLER.sub(" ", name)
    return re.sub(r"[^a-z0-9]", "", name)


def candidates(company: dict) -> list[str]:
    base = core(company["name"])
    plain = re.sub(r"[^a-z0-9]", "", re.sub(r"\(.*?\)", "", company["name"].lower()))
    slug = str(company.get("slug") or "").lower()
    out = [f"{base}.com", f"{base}.ai", f"{plain}.com", f"{plain}.ai", f"{base}.io"]
    if re.fullmatch(r"[a-z0-9-]+", slug):
        out += [f"{slug}.com", f"{slug}.ai"]
    seen, unique = set(), []
    for d in out:
        if len(d) > 4 and d not in seen:  # ".com" alone, from a name with no letters
            seen.add(d)
            unique.append(d)
    return unique


def names_company(page: str, company: str) -> bool:
    """True when the page's <title> or og:site_name contains the company's core name."""
    found = [m.group(1) for m in (_TITLE.search(page), _SITE_NAME.search(page)) if m]
    want = core(company)
    return bool(want) and any(want in re.sub(r"[^a-z0-9]", "", html.unescape(t).lower()) for t in found)


def allowed(client: HttpClient, domain: str) -> bool:
    try:
        text = client.get_text(f"https://{domain}/robots.txt", accept="text/plain")
    except FetchError:
        return True  # no answer about robots: the homepage request itself is the only one we make
    if not text:
        return True
    rp = RobotFileParser()
    rp.parse(text.splitlines())
    return rp.can_fetch(USER_AGENT, f"https://{domain}/")


def find(client: HttpClient, company: dict) -> str | None:
    for domain in candidates(company):
        try:
            if not allowed(client, domain):
                continue
            got = client.get_page(f"https://{domain}/")
        except (FetchError, OSError, ValueError):
            continue
        if got and names_company(got[1], company["name"]):
            # Keep where it landed (sarvam.com -> www.sarvam.ai), minus "www.".
            host = urlparse(got[0]).netloc or domain
            return host.removeprefix("www.")
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="check only the first N companies (for a trial run)")
    args = ap.parse_args()
    text = COMPANIES.read_text()
    companies = yaml.safe_load(text)["companies"]
    todo = [c for c in companies if c.get("verified") and not c.get("website")]
    if args.limit:
        todo = todo[: args.limit]
    client = HttpClient(retries=0, timeout=10.0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        found = dict(zip((c["name"] for c in todo), pool.map(lambda c: find(client, c), todo)))
    results = {c["name"]: {**c, "website": found[c["name"]]} for c in todo if found.get(c["name"])}
    for name, site in sorted(found.items()):
        print(f"{name}: {site or 'not found'}")
    print(f"\nFound {len(results)} of {len(todo)} companies without a website.")
    COMPANIES.write_text(rewrite_yaml(text, results))


if __name__ == "__main__":
    main()
