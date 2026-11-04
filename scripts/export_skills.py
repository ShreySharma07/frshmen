"""Write config/skills.yaml as JSON copies for the browser and the API.

The dashboard ticks a skill when the saved resume names it (site/src/lib/skills.json), and the
tailored resume's check refuses lines that add one (api/src/skills_catalogue.py), with the same terms and
rules the pipeline uses on postings (extract/skills.py). The Worker uploads only api/src's Python
modules, so the API's copy is a .py file. tests/test_skills.py fails when a copy differs.

Run: python scripts/export_skills.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "config" / "skills.yaml"
SITE = ROOT / "site" / "src" / "lib" / "skills.json"
API = ROOT / "api" / "src" / "skills_catalogue.py"


def _skills() -> list[dict]:
    raw = yaml.safe_load(SOURCE.read_text())
    return [{"name": s["name"], "terms": s["terms"], "exact": bool(s.get("exact", False))} for s in raw["skills"]]


def exported() -> str:
    # One skill per line, so a diff shows exactly which entry changed.
    return "[\n" + ",\n".join(json.dumps(s, ensure_ascii=False) for s in _skills()) + "\n]\n"


def exported_py() -> str:
    lines = ",\n".join(f"    {s!r}" for s in _skills())
    return ('"""Generated from config/skills.yaml by scripts/export_skills.py; edit the YAML, not this."""\n\n'
            f"SKILLS = [\n{lines},\n]\n")


if __name__ == "__main__":
    SITE.write_text(exported())
    API.write_text(exported_py())
    print(f"wrote {SITE.relative_to(ROOT)} and {API.relative_to(ROOT)}")
