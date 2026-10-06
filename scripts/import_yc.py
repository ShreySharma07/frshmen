"""Append hiring YC AI startups from the yc-oss dataset to config/companies.yaml.

yc-oss mirrors YC's public company directory as JSON on GitHub, so nothing is
scraped from ycombinator.com. New entries land unverified with a guessed
Ashby slug; scripts/verify_companies.py then finds their real board.

Filter (see docs/decisions.md): active, hiring, tagged AI/ML, batch 2021 or
later, and either 10+ people (more likely to post on an ATS and hire new
grads) or based in India.

Run: python scripts/import_yc.py [--source FILE_OR_URL] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "config" / "companies.yaml"
# raw.githubusercontent.com rather than yc-oss.github.io: same file, and reachable from more networks.
SOURCE = "https://raw.githubusercontent.com/yc-oss/api/main/companies/hiring.json"
USER_AGENT = "frshmen-job-board/0.1 (personal fresher job board; +https://github.com/ShreySharma07/frshmen)"

AI_TAGS = {
    "Artificial Intelligence", "AI", "Generative AI", "Machine Learning", "Computer Vision", "Deep Learning",
    "NLP", "Natural Language Processing", "AI Assistant", "Conversational AI", "LLM", "Speech Recognition",
    "MLOps", "Robotics", "AIOps",
}
MIN_BATCH_YEAR = 2021
MIN_TEAM_SIZE = 10
HQ_BY_REGION = {"India": "in", "United States of America": "us", "Canada": "ca", "United Kingdom": "uk"}
EU_REGION = "Europe"


def load_source(source: str) -> list[dict[str, Any]]:
    if source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    return json.loads(Path(source).read_text())


def batch_year(batch: str | None) -> int:
    m = re.search(r"\d{4}", batch or "")
    return int(m.group()) if m else 0


def is_candidate(c: dict[str, Any]) -> bool:
    regions = c.get("regions") or []
    return (
        c.get("status") == "Active"
        and c.get("isHiring") is not False
        and bool(AI_TAGS & set(c.get("tags") or []))
        and batch_year(c.get("batch")) >= MIN_BATCH_YEAR
        and ((c.get("team_size") or 0) >= MIN_TEAM_SIZE or "India" in regions)
    )


def hq(c: dict[str, Any]) -> str:
    regions = c.get("regions") or []
    for region, code in HQ_BY_REGION.items():
        if region in regions:
            return code
    return "eu" if EU_REGION in regions else "global"


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def new_entries(dataset: list[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known = {norm(c["name"]) for c in existing} | {norm(str(c["slug"])) for c in existing}
    out = []
    for c in sorted(dataset, key=lambda c: (-batch_year(c.get("batch")), c["name"].lower())):
        if not is_candidate(c) or norm(c["name"]) in known or norm(c["slug"]) in known:
            continue
        known.add(norm(c["name"]))
        out.append({"name": c["name"], "category": "yc", "hq": hq(c), "ats": "ashby",
                    "slug": c["slug"], "verified": False})
    return out


def append_section(text: str, entries: list[dict[str, Any]], today: str) -> str:
    lines = [f"\n  # --- YC AI startups imported from yc-oss on {today} (scripts/import_yc.py) ---\n"]
    for e in entries:
        body = yaml.safe_dump(e, default_flow_style=True, sort_keys=False, width=1000).strip()
        lines.append(f"  - {body}\n")
    return text.rstrip("\n") + "\n" + "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default=SOURCE, help="yc-oss hiring.json URL or local file")
    parser.add_argument("--dry-run", action="store_true", help="print what would be added")
    args = parser.parse_args()

    text = COMPANIES.read_text()
    entries = new_entries(load_source(args.source), yaml.safe_load(text)["companies"])
    for e in entries:
        print(f"+ {e['name']} ({e['hq']}, {e['slug']})")
    print(f"{len(entries)} new YC companies")
    if entries and not args.dry_run:
        COMPANIES.write_text(append_section(text, entries, date.today().isoformat()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
