"""One general category per job, from its title (config/role_families.yaml).

Separate from extract/role.py: that decides whether a job is one of Shrey's roles (and some
sources fetch only those); this sorts every job, for people whose roles are different.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from extract.role import _phrase

CONFIG = Path(__file__).resolve().parent.parent / "config" / "role_families.yaml"
FALLBACK = "other"


@lru_cache(maxsize=1)
def _rules() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    raw = yaml.safe_load(CONFIG.read_text())["categories"]
    return tuple((c["key"], c["label"], tuple(t.lower() for t in c["titles"])) for c in raw)


CATEGORIES: dict[str, str] = {key: label for key, label, _ in _rules()} | {FALLBACK: "Other"}


def job_category(title: str, role_family: str | None = None) -> str:
    """A plain "Software Engineer" that passed Shrey's Python + AI/ML check (role family
    generic_swe) is an AI/ML job: its description says so even though its title doesn't."""
    return "ai_ml" if role_family == "generic_swe" else category(title)


def category(title: str) -> str:
    t = title.lower()
    for key, _, titles in _rules():
        if any(_phrase(t, p) for p in titles):
            return key
    return FALLBACK
