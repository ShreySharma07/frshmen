"""Split a description into clauses that know which section they sit in.

A "2+ years" under "Nice to have" must not reject a fresher role, so every
clause carries whether its section is preferred. Clauses are the unit the
other extractors look at, and the text kept as evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# "Ideally you'd have:" is deliberately absent: Scale AI uses it for the main
# requirements and puts the real extras under "Nice to haves:".
_PREFERRED_HEADING = re.compile(
    r"prefer|nice[- ]to[- ]have|good[- ]to[- ]have|bonus|\bplus\b|desir|extra credit|stand out|added advantage",
    re.I,
)
_HEADING_WORDS = re.compile(
    r"require|qualif|must|who you are|what you('ll)? (need|bring)|you (have|bring|are)|about (you|the role)|"
    r"responsib|what you('ll)? do|the role|skills|experience|education|basic|minimum|benefits|perks|about us",
    re.I,
)
# Don't end a sentence after these ("min. 1-2 years" must stay one clause).
_ABBREV = re.compile(r"\b(min|max|approx|e\.g|i\.e|etc|vs|incl|yrs?|exp|no|sr|jr|st|dept)\.$", re.I)


@dataclass(frozen=True)
class Clause:
    text: str
    preferred_section: bool


def _is_heading(line: str) -> bool:
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > 60 or stripped.startswith(("-", "•", "*")):
        return False
    if line.strip().endswith(":"):
        return True
    # Short title-ish lines with no colon, e.g. "Bonus Points" or "Requirements". Longer ones
    # are requirements themselves ("Articleship in Big 4 preferred"), not section headings.
    if len(stripped.split()) > 4 or re.search(r"\d", stripped):  # "2-4 years of experience" is content
        return False
    return not re.search(r"[.!?;,]$", stripped) and bool(
        _HEADING_WORDS.search(stripped) or _PREFERRED_HEADING.search(stripped)
    )


def _sentences(line: str) -> list[str]:
    parts: list[str] = []
    buf = ""
    for piece in re.split(r"(?<=[.!?;])\s+", line):
        buf = f"{buf} {piece}".strip() if buf else piece
        # Keep going if the split happened after an abbreviation or before a lowercase/digit.
        if _ABBREV.search(buf):
            continue
        parts.append(buf)
        buf = ""
    if buf:
        parts.append(buf)
    return [p.strip(" -•*\t") for p in parts if p.strip(" -•*\t")]


def clauses(text: str) -> list[Clause]:
    out: list[Clause] = []
    preferred = False
    for line in text.splitlines():
        if _is_heading(line):
            preferred = bool(_PREFERRED_HEADING.search(line))
            continue
        for sentence in _sentences(line):
            out.append(Clause(sentence, preferred))
    return out
