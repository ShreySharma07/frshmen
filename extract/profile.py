"""Load config/profile.yaml into a typed object so nothing about Shrey is hardcoded."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "profile.yaml"

# Title phrases that mark the backend family; the rest of `include` is AI/ML.
BACKEND_PHRASES = ("backend", "back end", "back-end", "python engineer", "python developer")


@dataclass(frozen=True)
class Profile:
    exact_batch: frozenset[int]
    soft_batch: frozenset[int]
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    intern_requires_conversion: bool
    backend_requires_any: tuple[str, ...]
    generic_swe_enabled: bool
    generic_swe_titles: tuple[str, ...]
    generic_swe_groups: tuple[tuple[str, ...], ...]
    mobile_titles: tuple[str, ...] = ()
    mobile_generic_titles: tuple[str, ...] = ()
    mobile_requires_any: tuple[str, ...] = ()
    skills: tuple[str, ...] = field(default_factory=tuple)


@lru_cache(maxsize=4)
def load_profile(path: Path = DEFAULT_PATH) -> Profile:
    raw = yaml.safe_load(Path(path).read_text())
    roles = raw.get("target_roles", {})
    swe = raw.get("generic_swe", {})
    mobile = raw.get("mobile", {})
    return Profile(
        exact_batch=frozenset(raw.get("batch_years", {}).get("exact", [])),
        soft_batch=frozenset(raw.get("batch_years", {}).get("soft", [])),
        include=tuple(p.lower() for p in roles.get("include", [])),
        exclude=tuple(p.lower() for p in roles.get("exclude", [])),
        intern_requires_conversion=bool(roles.get("intern_requires_conversion", True)),
        backend_requires_any=tuple(p.lower() for p in raw.get("backend_requires_any", [])),
        generic_swe_enabled=bool(swe.get("enabled", False)),
        generic_swe_titles=tuple(p.lower() for p in swe.get("titles", [])),
        generic_swe_groups=tuple(tuple(w.lower() for w in group) for group in swe.get("requires_all_groups", [])),
        skills=tuple(s.lower() for s in raw.get("skills", [])),
        mobile_titles=tuple(p.lower() for p in mobile.get("titles", [])),
        mobile_generic_titles=tuple(p.lower() for p in mobile.get("generic_titles", [])),
        mobile_requires_any=tuple(p.lower() for p in mobile.get("requires_any", [])),
    )
