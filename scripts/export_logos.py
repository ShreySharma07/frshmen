"""Write site/public/company-domains.json: company name -> website domain, for the job list's logos.

A static file the page fetches once (not bundled into its JavaScript), from `website` in
config/companies.yaml. A company missing here gets a tinted letter instead (docs/decisions.md,
2026-11-04). tests/test_logos.py fails when it is out of date.

Run: python scripts/export_logos.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "config" / "companies.yaml"
TARGET = ROOT / "site" / "public" / "company-domains.json"


def domain(website: str) -> str | None:
    host = re.sub(r"^https?://", "", website.strip().lower()).split("/")[0].removeprefix("www.")
    return host if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", host) else None


def exported() -> str:
    companies = yaml.safe_load(SOURCE.read_text())["companies"]
    pairs = {c["name"]: d for c in companies if c.get("website") and (d := domain(str(c["website"])))}
    return json.dumps(dict(sorted(pairs.items())), ensure_ascii=False, separators=(",", ":")) + "\n"


if __name__ == "__main__":
    TARGET.write_text(exported())
    print(f"wrote {TARGET.relative_to(ROOT)}")
