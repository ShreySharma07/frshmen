"""Which catalogued skills a text names (config/skills.yaml).

Used on each posting's full text by the pipeline, and mirrored in the browser for resumes
(site/src/lib/skills.ts), so "asked in 40% of your matches" and "on your resume" count the same
words. A hit is the skill's own word, so the text itself is the evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "skills.yaml"
# Whole words, where "+" and "#" count as word characters so "C" doesn't match inside "C++".
_EDGE_BEFORE = r"(?<![A-Za-z0-9+#])"
_EDGE_AFTER = r"(?![A-Za-z0-9+#])"


@dataclass(frozen=True)
class Skill:
    name: str
    terms: tuple[str, ...]
    exact: bool
    pattern: re.Pattern[str]


def _compile(terms: tuple[str, ...], exact: bool) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(f"{_EDGE_BEFORE}(?:{alternatives}){_EDGE_AFTER}", 0 if exact else re.IGNORECASE)


@lru_cache(maxsize=4)
def load_skills(path: Path = DEFAULT_PATH) -> tuple[Skill, ...]:
    raw = yaml.safe_load(Path(path).read_text())
    out = []
    for entry in raw["skills"]:
        terms = tuple(str(t) for t in entry["terms"])
        exact = bool(entry.get("exact", False))
        out.append(Skill(str(entry["name"]), terms, exact, _compile(terms, exact)))
    return tuple(out)


def skills_in(text: str | None, catalogue: tuple[Skill, ...] | None = None) -> list[str]:
    """Names of the skills the text mentions, in catalogue order."""
    if not text:
        return []
    return [s.name for s in (catalogue or load_skills()) if s.pattern.search(text)]
