"""Is this a role Shrey targets? Title first, description only to confirm.

Families: "ai_ml", "backend" (Python stack only), "mobile" (Android / React Native)
and "generic_swe" (plain Software Engineer titles whose description shows Python and
AI/ML work). Excluded titles (frontend, iOS-only, QA, sales, ...) lose even if they
also match an include; a title naming Android or React Native is exempt from the
mobile-related excludes ("iOS/Android Engineer" is still a fit).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from extract.profile import BACKEND_PHRASES, Profile

# Excludes that a title naming Android / React Native overrides ("iOS & Android Developer").
_MOBILE_EXCLUDES = {"ios", "mobile"}
_INTERN = re.compile(r"\bintern(ship)?s?\b", re.I)
_CONVERSION = re.compile(
    r"conver(t|sion|ted)\b[^.\n]{0,60}(full[- ]time|permanent|offer)|full[- ]time (offer|conversion|role after)|"
    r"pre[- ]placement offer|\bPPO\b|return offer",
    re.I,
)


@dataclass
class RoleMatch:
    is_target: bool
    family: str | None
    reason: str
    evidence: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"role_match": self.is_target, "role_family": self.family, "role_reason": self.reason,
                "role_evidence": self.evidence}


def _phrase(text: str, phrase: str) -> bool:
    # Whole words, but "/" and "," count as boundaries: "AI/ML Infrastructure" has "ml infrastructure".
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _snippet(description: str, words: tuple[str, ...]) -> str | None:
    for line in description.splitlines():
        if any(_phrase(line.lower(), w) for w in words):
            return line.strip()
    return None


def match_role(title: str, description: str, profile: Profile) -> RoleMatch:
    t = title.lower()
    evidence = [{"kind": "title", "snippet": title}]
    mobile_title = next((p for p in profile.mobile_titles if _phrase(t, p)), None)
    generic_mobile = None if mobile_title else next((p for p in profile.mobile_generic_titles if _phrase(t, p)), None)
    excludes = profile.exclude
    if mobile_title or generic_mobile:
        excludes = tuple(p for p in excludes if p not in _MOBILE_EXCLUDES)
    excluded = next((p for p in excludes if _phrase(t, p)), None)
    if excluded:
        return RoleMatch(False, None, f"title has excluded {excluded!r}", evidence)

    hit = mobile_title or generic_mobile or next((p for p in profile.include if _phrase(t, p)), None)
    family = None
    if mobile_title or generic_mobile:
        family = "mobile"
    elif hit:
        family = "backend" if any(b in hit for b in BACKEND_PHRASES) else "ai_ml"
    elif profile.generic_swe_enabled and any(_phrase(t, p) for p in profile.generic_swe_titles):
        family = "generic_swe"
    if family is None:
        return RoleMatch(False, None, "title matches no target role", evidence)

    if generic_mobile:
        found = _snippet(description, profile.mobile_requires_any)
        if not found:
            return RoleMatch(False, family, "mobile role without an Android / React Native stack", evidence)
        evidence.append({"kind": "mobile_stack", "snippet": found})

    if family == "backend":
        found = _snippet(description, profile.backend_requires_any)
        if not found:
            return RoleMatch(False, family, "backend role without a Python stack", evidence)
        evidence.append({"kind": "python_stack", "snippet": found})

    if family == "generic_swe":
        for group in profile.generic_swe_groups:
            found = _snippet(description, group)
            if not found:
                return RoleMatch(False, family, f"software role without any of {list(group)[:4]}...", evidence)
            evidence.append({"kind": "swe_requirement", "snippet": found})

    if profile.intern_requires_conversion and _INTERN.search(title):
        m = _CONVERSION.search(description)
        if not m:
            return RoleMatch(False, family, "internship without stated full-time conversion", evidence)
        evidence.append({"kind": "conversion", "snippet": _line_of(description, m.start())})

    why = f"title matches {hit!r}" if hit else "software role with Python and AI/ML in the description"
    return RoleMatch(True, family, why, evidence)


def _line_of(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return text[start: end if end != -1 else len(text)].strip()
