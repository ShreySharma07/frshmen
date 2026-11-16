"""What kinds of work a startup likely hires for, from what it builds (config/startup_tags.yaml).

Used by scripts/refresh_startups.py to fill startup_profiles, which the agent's suggest_startups
compares with a person's saved kinds of work and resume skills (docs/decisions.md, 2026-11-16).
Rules only: a startup with no description gets no categories, never a guess from its name.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml

from extract.skills import skills_in

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "startup_tags.yaml"
# A web or backend product hires general software and full-stack engineers too, and people
# save those kinds of work on their profile.
_IMPLIES = {"backend": ("software", "fullstack"), "frontend": ("software", "fullstack")}


@lru_cache(maxsize=2)
def _rules(path: Path = DEFAULT_PATH) -> list[tuple[str, frozenset[str], re.Pattern[str] | None]]:
    raw = yaml.safe_load(Path(path).read_text())["categories"]
    out = []
    for key, rule in raw.items():
        words = sorted((str(w) for w in rule.get("words") or []), key=len, reverse=True)
        pattern = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(w) for w in words) + r")(?![A-Za-z0-9])",
                             re.IGNORECASE) if words else None
        out.append((str(key), frozenset(str(t).lower() for t in rule.get("tags") or []), pattern))
    return out


def categories_for(tags: Iterable[str], text: str | None) -> list[str]:
    """Category keys whose YC tags or description words appear, in config order, then implied ones."""
    have = {t.strip().lower() for t in tags if t}
    found = [key for key, rule_tags, pattern in _rules()
             if have & rule_tags or (pattern is not None and text and pattern.search(text))]
    for key in list(found):
        found += [k for k in _IMPLIES.get(key, ()) if k not in found]
    return found


def profile(tags: Iterable[str], text: str | None) -> dict[str, list[str]]:
    tags = list(tags)
    joined = " ".join(filter(None, [text, *tags]))
    return {"categories": categories_for(tags, text), "skills": skills_in(joined)}
