"""Fill startup_profiles: what each startup on the YC founders list builds (docs/decisions.md, 2026-11-16).

The agent's suggest_startups ranks startups by how well what they build fits a person, whether or not
they have an opening on Aventra, so each founder's company needs a description. In order:
  1. the uploaded CSV's description column (contacts.description),
  2. the yc-oss dataset (YC's public directory mirrored on GitHub: one-liner, description, tags),
  3. the startup's own homepage <meta name="description">, read at most once per 30 days, only where
     robots.txt allows, with our User-Agent and ETag / If-Modified-Since.
A startup with none of these keeps no description and no categories; it is never guessed from its name.

Only new or changed rows are written (Supabase free tier). Weekly in GitHub Actions, or by hand after
uploading a founders list:  SUPABASE_DB_URL=... python scripts/refresh_startups.py [--no-homepages]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from extract.startup import profile  # noqa: E402
from sources.http import USER_AGENT, HttpClient  # noqa: E402

YC_ALL = "https://raw.githubusercontent.com/yc-oss/api/main/companies/all.json"
HOMEPAGE_EVERY = timedelta(days=30)
MAX_HOMEPAGES = 150  # per run; the rest wait for next week
MAX_HTML = 400_000  # the <head> is near the top; never read a whole large page
STATUS_NOTE = re.compile(r"Company status:\s*([A-Za-z]+)", re.IGNORECASE)
_META = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r"""([a-zA-Z:-]+)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""")

FOUNDER_COMPANIES = """
    SELECT lower(btrim(company)) AS key, min(btrim(company)) AS name, min(company_url) AS website,
           string_agg(DISTINCT description, ' ') AS csv_description, string_agg(DISTINCT notes, '; ') AS notes
    FROM contacts WHERE kind = 'founder' GROUP BY 1"""
FIELDS = ("name", "website", "one_liner", "description", "tags", "status", "source", "categories", "skills",
          "homepage_tried_at", "homepage_etag", "homepage_modified")


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def domain(url: str | None) -> str:
    return re.sub(r"^www\.", "", re.sub(r"^https?://", "", (url or "").strip()).split("/")[0].lower())


def index_yc(dataset: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """yc-oss companies by normalised name and by website domain. A name shared by two companies
    (it happens) is dropped from the name index, so only the domain can match those."""
    out: dict[str, dict[str, Any]] = {}
    seen: dict[str, int] = {}
    for c in dataset:
        n = norm(c.get("name", ""))
        if n:
            seen[n] = seen.get(n, 0) + 1
            out[f"name:{n}"] = c
        d = domain(c.get("website"))
        if d:
            out[f"site:{d}"] = c
    for n, count in seen.items():
        if count > 1:
            out.pop(f"name:{n}", None)
    return out


def find_yc(index: dict[str, dict[str, Any]], name: str, website: str | None) -> dict[str, Any] | None:
    # The website is the stronger tie (two startups can share a name, not a domain).
    return (website and index.get(f"site:{domain(website)}")) or index.get(f"name:{norm(name)}")


def meta_description(html: str) -> str | None:
    """<meta name="description"> or, failing that, og:description, as plain text."""
    found: dict[str, str] = {}
    for tag in _META.findall(html):
        attrs = {k.lower(): v.strip("\"'") for k, v in _ATTR.findall(tag)}
        key = (attrs.get("name") or attrs.get("property") or "").lower()
        if key in ("description", "og:description") and attrs.get("content", "").strip():
            found.setdefault(key, " ".join(unescape(attrs["content"]).split()))
    return found.get("description") or found.get("og:description")


Fetch = Callable[[str, str | None, str | None], tuple[int, str | None, str | None, str | None]]


def fetch_homepage(url: str, etag: str | None, modified: str | None) -> tuple[int, str | None, str | None, str | None]:
    """(HTTP status, description, ETag, Last-Modified). 304 means unchanged since the stored copy."""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as resp:
            html = resp.read(MAX_HTML).decode("utf-8", errors="replace")
            return resp.status, meta_description(html), resp.headers.get("ETag"), resp.headers.get("Last-Modified")
    except urllib.error.HTTPError as e:
        return e.code, None, None, None
    except Exception:  # dead domain, TLS error, timeout: try again in 30 days
        return 0, None, None, None


def build(company: dict[str, Any], yc: dict[str, Any] | None, old: dict[str, Any] | None, now: datetime,
          fetch: Fetch | None, allowed: Callable[[str], bool]) -> tuple[dict[str, Any], bool]:
    """The startup_profiles row for one company, and whether its homepage was fetched."""
    old = old or {}
    row: dict[str, Any] = {"name": company["name"], "website": company["website"] or (yc or {}).get("website") or None,
                           "one_liner": None, "description": None, "tags": [], "status": None, "source": None,
                           "homepage_tried_at": old.get("homepage_tried_at"), "homepage_etag": old.get("homepage_etag"),
                           "homepage_modified": old.get("homepage_modified")}
    if row["website"] and not re.match(r"^https?://", row["website"]):
        row["website"] = "https://" + row["website"]
    if yc:
        tags = [*(yc.get("tags") or []), *(yc.get("industries") or [])]
        row["tags"] = list(dict.fromkeys(str(t) for t in tags if t))[:30]
        row["status"] = yc.get("status") or None
    note = STATUS_NOTE.search(company.get("notes") or "")
    if note and not row["status"]:
        row["status"] = note.group(1).capitalize()

    if company.get("csv_description"):
        row["one_liner"], row["source"] = company["csv_description"][:300], "csv"
        row["description"] = company["csv_description"][:1000] if len(company["csv_description"]) > 300 else None
    elif yc and (yc.get("one_liner") or yc.get("long_description")):
        row["one_liner"] = (yc.get("one_liner") or yc["long_description"])[:300]
        row["description"] = (yc.get("long_description") or "")[:1000] or None
        row["source"] = "yc-oss"
    elif old.get("source") == "homepage":
        row["one_liner"], row["source"] = old.get("one_liner"), "homepage"

    fetched = False
    tried = old.get("homepage_tried_at")
    due = tried is None or now - tried >= HOMEPAGE_EVERY
    if row["source"] in (None, "homepage") and row["website"] and fetch and due and allowed(row["website"]):
        fetched = True
        status, desc, etag, modified = fetch(row["website"], row["homepage_etag"], row["homepage_modified"])
        row["homepage_tried_at"] = now
        if status == 200 and desc:
            row.update(one_liner=desc[:300], source="homepage", homepage_etag=etag, homepage_modified=modified)
        elif status != 304:
            row.update(one_liner=None, source=None, homepage_etag=None, homepage_modified=None)

    text = " ".join(filter(None, [row["one_liner"], row["description"]]))
    row.update(profile(row["tags"], text) if text or row["tags"] else {"categories": [], "skills": []})
    return row, fetched


def changed(row: dict[str, Any], old: dict[str, Any] | None) -> bool:
    return old is None or any(row[f] != old.get(f) for f in FIELDS)


def refresh(pg: Any, dataset: list[dict[str, Any]], fetch: Fetch | None, allowed: Callable[[str], bool],
            now: datetime | None = None, max_homepages: int = MAX_HOMEPAGES) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    index = index_yc(dataset)
    cur = pg.cursor()
    cols = [d for d in ("key", *FIELDS)]
    existing = {r[0]: dict(zip(cols, r)) for r in cur.execute(f"SELECT {', '.join(cols)} FROM startup_profiles")}
    companies = [dict(zip(("key", "name", "website", "csv_description", "notes"), r)) for r in cur.execute(FOUNDER_COMPANIES)]
    counts = {"companies": len(companies), "written": 0, "homepages": 0, "described": 0, "removed": 0}
    for c in companies:
        budget = fetch if counts["homepages"] < max_homepages else None
        row, fetched = build(c, find_yc(index, c["name"], c["website"]), existing.get(c["key"]), now, budget, allowed)
        counts["homepages"] += fetched
        counts["described"] += bool(row["one_liner"])
        if changed(row, existing.get(c["key"])):
            cur.execute(f"""INSERT INTO startup_profiles (key, {', '.join(FIELDS)}, updated_at)
                            VALUES (%s, {', '.join(['%s'] * len(FIELDS))}, now())
                            ON CONFLICT (key) DO UPDATE SET {', '.join(f'{f} = EXCLUDED.{f}' for f in FIELDS)},
                            updated_at = now()""", [c["key"], *(row[f] for f in FIELDS)])
            counts["written"] += 1
    # Startups whose founders were deleted from the list (a removal request) go too.
    gone = [k for k in existing if k not in {c["key"] for c in companies}]
    if gone:
        cur.execute("DELETE FROM startup_profiles WHERE key = ANY(%s)", [gone])
        counts["removed"] = len(gone)
    return counts


def main() -> None:
    import psycopg

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-homepages", action="store_true", help="use the CSV and yc-oss only")
    ap.add_argument("--source", default=YC_ALL, help="yc-oss all.json, as a URL or a file")
    args = ap.parse_args()
    url = os.environ.get("SUPABASE_DB_URL") or sys.exit("set SUPABASE_DB_URL")
    if args.source.startswith("https://"):
        req = urllib.request.Request(args.source, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:
            dataset = json.load(resp)
    else:
        dataset = json.loads(Path(args.source).read_text())
    from detect_careers import Robots

    robots = Robots(HttpClient(retries=1, timeout=15))
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as pg:
        counts = refresh(pg, dataset, None if args.no_homepages else fetch_homepage, robots.allowed)
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
