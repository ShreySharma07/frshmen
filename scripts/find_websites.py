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

# Legal and filler words dropped from a name before comparing it with a page title. "AI" and
# "Labs" stay: "Character.AI" must not match a page about some other "Character".
_FILLER = re.compile(r"\b(inc|llc|ltd|limited|corp|corporation|technologies|technology|hq|the|co)\b")
# A short name ("Flint", "Weave") is shared by many companies, so its site must also link to the
# company's own hiring board before we believe it.
DISTINCTIVE = 8
ATS_LINK = {"greenhouse": "greenhouse.io/{}", "lever": "lever.co/{}", "ashby": "ashbyhq.com/{}",
            "workable": "workable.com/{}", "smartrecruiters": "smartrecruiters.com/{}"}
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_SITE_NAME = re.compile(r"<meta[^>]+property=[\"']og:site_name[\"'][^>]+content=[\"']([^\"']+)", re.I)


def core(name: str) -> str:
    """'Sarvam AI' -> 'sarvamai', 'Anysphere (Cursor)' -> 'anysphere': what a page title must contain."""
    name = re.sub(r"\(.*?\)", " ", name.lower())
    name = _FILLER.sub(" ", name)
    return re.sub(r"[^a-z0-9]", "", name)


def candidates(company: dict) -> list[str]:
    words = re.sub(r"\(.*?\)", " ", company["name"].lower())
    full = core(company["name"])
    # Without a trailing "AI": "Sarvam AI" is sarvam.ai far more often than sarvamai.com.
    short = re.sub(r"[^a-z0-9]", "", re.sub(r"(\.ai|\s+ai)\s*$", "", words))
    slug = str(company.get("slug") or "").lower()
    ai_named = bool(re.search(r"(\.ai|\bai)\s*$", words))
    out = ([f"{short}.ai", f"{short}.com"] if ai_named else [f"{short}.com", f"{short}.ai"]) + [f"{full}.com", f"{short}.io"]
    if re.fullmatch(r"[a-z0-9-]+", slug):
        out += [f"{slug}.com", f"{slug}.ai"]
    seen, unique = set(), []
    for d in out:
        if len(d) > 4 and d not in seen:  # ".com" alone, from a name with no letters
            seen.add(d)
            unique.append(d)
    return unique


def links_board(page: str, company: dict) -> bool:
    """True when the page links to the company's own board on its hiring system."""
    pattern = ATS_LINK.get(str(company.get("ats")))
    slug = str(company.get("slug") or "")
    return bool(pattern and slug) and pattern.format(slug).lower() in page.lower()


def names_company(page: str, company: str) -> bool:
    """True when the page's <title> or og:site_name contains the company's core name."""
    found = [m.group(1) for m in (_TITLE.search(page), _SITE_NAME.search(page)) if m]
    want = core(company)
    return bool(want) and any(want in re.sub(r"[^a-z0-9]", "", html.unescape(t).lower()) for t in found)


def allowed(client: HttpClient, domain: str, path: str = "/") -> bool:
    try:
        text = client.get_text(f"https://{domain}/robots.txt", accept="text/plain")
    except FetchError:
        return True  # no answer about robots: the homepage request itself is the only one we make
    if not text:
        return True
    rp = RobotFileParser()
    rp.parse(text.splitlines())
    return rp.can_fetch(USER_AGENT, f"https://{domain}{path}")


def same_site(final_url: str, domain: str, company: str) -> str | None:
    """The host a candidate ended up on, if it's still the company's own: sarvam.com -> sarvam.ai
    is fine, a redirect to linkedin.com or a parking page isn't."""
    host = (urlparse(final_url).hostname or "").removeprefix("www.")
    if host == domain or host.endswith("." + domain):
        return host
    label = re.sub(r"[^a-z0-9]", "", host.split(".")[0])
    want = core(company)
    return host if label and (label in want or want.startswith(label)) and len(label) >= 3 else None


def find(client: HttpClient, company: dict) -> str | None:
    distinctive = len(core(company["name"])) >= DISTINCTIVE
    for domain in candidates(company):
        try:
            if not allowed(client, domain):
                continue
            got = client.get_page(f"https://{domain}/")
            if not got or not names_company(got[1], company["name"]):
                continue
            host = same_site(got[0], domain, company["name"])
            if not host:
                continue
            if not distinctive:
                careers = client.get_page(f"https://{host}/careers") if allowed(client, host, "/careers") else None
                if not (links_board(got[1], company) or (careers and links_board(careers[1], company))):
                    continue
            return host
        except (FetchError, OSError, ValueError):
            continue
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
