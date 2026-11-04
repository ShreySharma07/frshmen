"""Write config/skills.yaml as site/src/lib/skills.json, the browser's copy of the catalogue.

The dashboard ticks a skill when the saved resume names it, with the same terms and rules the
pipeline uses on postings (extract/skills.py). tests/test_skills.py fails when the copies differ.

Run: python scripts/export_skills.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "config" / "skills.yaml"
TARGET = ROOT / "site" / "src" / "lib" / "skills.json"


def exported() -> str:
    raw = yaml.safe_load(SOURCE.read_text())
    skills = [{"name": s["name"], "terms": s["terms"], "exact": bool(s.get("exact", False))} for s in raw["skills"]]
    # One skill per line, so a diff shows exactly which entry changed.
    return "[\n" + ",\n".join(json.dumps(s, ensure_ascii=False) for s in skills) + "\n]\n"


if __name__ == "__main__":
    TARGET.write_text(exported())
    print(f"wrote {TARGET.relative_to(ROOT)}")
