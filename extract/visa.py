"""Visa sponsorship and relocation, read from the description with the sentence as evidence.

Used only to decide whether a role abroad is reachable for Shrey (profile:
Europe/US only with sponsorship or explicit relocation). A "no" anywhere wins
over a "yes": "we sponsor visas for some roles, but not this one" must read as no.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_NO = re.compile(
    r"\b(not|unable to|cannot|can't|can ?not|won't|will not|do not|don't|does not|doesn't|is not able to|are not able to)"
    r"\s+(?:\w+\s+){0,3}?(sponsor|provide (?:visa )?sponsorship|offer (?:visa )?sponsorship|support (?:visa|work permit))|"
    r"\bno (visa |immigration )?sponsorship\b|\bsponsorship (is |will )?not (be )?(available|provided|offered)\b|"
    r"\bwithout (the need for |requiring )?(current or future )?(visa |employer )?sponsorship\b|"
    r"\bnot eligible for (visa )?sponsorship\b",
    re.I,
)
_YES = re.compile(
    r"\bvisa sponsorship (is |will be )?(available|provided|offered|possible)\b|"
    r"\b(we|company) (will |can |do |does |may )?(sponsor|provide sponsorship|offer sponsorship)\b|"
    r"\bsponsorship (is |will be )?(available|provided|offered)\b|\bwill sponsor\b|\bh-?1b sponsorship (is )?(available|offered)\b|"
    r"\bwe sponsor (visas?|work visas?|h-?1b)\b|\bvisa support\b|\bwork permit support\b",
    re.I,
)
_RELOCATION = re.compile(
    r"\brelocation (assistance|support|package|bonus|allowance)\b|\b(we|company) (will |can )?(help|assist|support) (you )?(with )?(your )?relocat\w*\b|"
    r"\brelocation (is |will be )?(provided|offered|available|covered)\b|\bwilling to relocate you\b",
    re.I,
)


@dataclass
class Visa:
    sponsorship: str  # yes | no | unknown
    relocation: bool
    evidence: list[dict[str, str]] = field(default_factory=list)


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(c, 0, start) for c in ".\n") + 1
    rights = [i for i in (text.find(c, end) for c in ".\n") if i != -1]
    return text[left: min(rights) + 1 if rights else len(text)].strip()


def extract_visa(description: str) -> Visa:
    text = description or ""
    evidence: list[dict[str, str]] = []
    no = _NO.search(text)
    yes = None if no else _YES.search(text)
    reloc = _RELOCATION.search(text)
    if no:
        evidence.append({"kind": "visa_no", "snippet": _sentence(text, no.start(), no.end())})
    elif yes:
        evidence.append({"kind": "visa_yes", "snippet": _sentence(text, yes.start(), yes.end())})
    if reloc:
        evidence.append({"kind": "relocation", "snippet": _sentence(text, reloc.start(), reloc.end())})
    return Visa("no" if no else "yes" if yes else "unknown", bool(reloc), evidence)
