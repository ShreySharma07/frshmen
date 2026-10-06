"""Find years-of-experience requirements, with the sentence each came from.

Only numbers that are clearly about the candidate's experience count:
"5 years of company history" or "within the last 1-2 years" are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from extract.sections import Clause

_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
}
_NUM = r"(?:\d{1,2}(?:\.\d)?|" + "|".join(_WORDS) + r")(?:\s*\(\d{1,2}\))?"
_UNIT = r"(?P<unit>years?|yrs?|months?|mos?)\b"

# Order matters: ranges and "+" forms before the bare number.
_PATTERNS = [
    re.compile(rf"(?P<a>{_NUM})\s*\+?\s*(?:-|–|—|to)\s*(?P<b>{_NUM})\s*\+?\s*{_UNIT}", re.I),
    re.compile(rf"(?P<a>{_NUM})\s*\+\s*{_UNIT}", re.I),
    re.compile(rf"(?P<a>{_NUM})\s*{_UNIT}\s*\+", re.I),
    re.compile(rf"(?P<a>{_NUM})\s*{_UNIT}\s*or\s*more", re.I),
    re.compile(rf"(?:up\s*to|less\s*than|under|maximum\s*(?:of\s*)?)\s*(?P<b>{_NUM})\s*{_UNIT}", re.I),
    re.compile(rf"(?P<a>{_NUM})\s*{_UNIT}", re.I),
]
_AT_LEAST = re.compile(r"(at\s*least|minimum(\s*of)?|min\.?|over|more\s*than|in\s*excess\s*of)\s*$", re.I)

# Words that make a nearby number about experience.
_EXPERIENCE_CONTEXT = re.compile(
    r"\bexp(erience[ds]?)?\b|\bwork(ing|ed)?\b|\bindustry\b|\bprofessional\b|hands[- ]on|track record|"
    r"\bpost[- ]qualification\b|\bin (a|the) (similar|relevant|related) role\b",
    re.I,
)
# "N years in/of/as/with/building ..." reads as experience even without the word.
_FOLLOWED_BY = re.compile(
    r"^\s*(?:of|in|on|as|at|with|working|building|developing|designing|leading|managing|owning|operating|"
    r"shipping|writing|doing|running|experience|exp|relevant|professional|industry|post|\w+ing)\b",
    re.I,
)
# Numbers that describe time, not the candidate: company history, deadlines, ages, durations.
_NOT_EXPERIENCE_BEFORE = re.compile(
    r"(?:^|[.;:]\s*)for\s*$|"  # sentence-opening "For 10 years, Scale has ..."
    r"\b(past|last|next|coming|within|since|after|every|first|for\s+the\s+(past|last)|over\s+the\s+(past|last)|"
    r"founded|history|ago|age|aged)\s*(?:the\s*)?(?:past\s*|last\s*)?$",
    re.I,
)
_NOT_EXPERIENCE_AFTER = re.compile(
    r"^\s*(?:old|ago|of\s+(?:age|funding|growth|history|operation|existence)|in\s+business|"
    r"degree|program|programme|course|contract|warranty|vesting|cliff|cycle|term|plan|roadmap|history)\b",
    re.I,
)
_HYPHEN_ADJ = re.compile(r"-\s*(year|month)\b", re.I)  # "4-year degree", "6-month contract"
_PREFERRED_CUE = re.compile(
    r"prefer|nice[- ]to[- ]have|good[- ]to[- ]have|\bbonus\b|\ba plus\b|is a plus|\bideal(ly)?\b|desir|"
    r"added advantage|an advantage|would be great",
    re.I,
)


@dataclass(frozen=True)
class YoeMention:
    min_years: float
    max_years: float | None  # None = open-ended ("3+ years")
    required: bool
    evidence: str


def _to_years(raw: str, unit: str) -> float:
    raw = re.sub(r"\(\d+\)", "", raw).strip().lower()
    value = float(_WORDS[raw]) if raw in _WORDS else float(raw)
    return value / 12 if unit.lower().startswith("mo") else value


def _subclauses(text: str) -> list[str]:
    """Commas split "8+ years of X, agentic AI is a plus" so the "plus" doesn't leak onto the 8."""
    return [p for p in re.split(r",\s+(?=[a-zA-Z])|\s+but\s+", text) if p.strip()]


def find_mentions(clauses: list[Clause]) -> list[YoeMention]:
    found: list[YoeMention] = []
    for clause in clauses:
        for part in _subclauses(clause.text):
            # Parentheticals often carry their own cue: "(PhD preferred)" isn't about the years.
            cue_text = re.sub(r"\([^)]*\)", "", part)
            preferred = clause.preferred_section or bool(_PREFERRED_CUE.search(cue_text))
            taken: list[tuple[int, int]] = []
            for pattern in _PATTERNS:
                for m in pattern.finditer(part):
                    if any(s < m.end() and m.start() < e for s, e in taken):
                        continue
                    mention = _mention(part, m, preferred, clause.text)
                    taken.append((m.start(), m.end()))
                    if mention:
                        found.append(mention)
    return found


def _mention(text: str, m: re.Match[str], preferred: bool, evidence: str) -> YoeMention | None:
    before, after = text[: m.start()], text[m.end():]
    if _HYPHEN_ADJ.search(m.group(0)) or _NOT_EXPERIENCE_BEFORE.search(before) or _NOT_EXPERIENCE_AFTER.search(after):
        return None
    if not (_FOLLOWED_BY.search(after) or _EXPERIENCE_CONTEXT.search(text) or _EXPERIENCE_CONTEXT.search(evidence)):
        return None
    unit = m.group("unit")
    groups = m.groupdict()
    a = _to_years(groups["a"], unit) if groups.get("a") else None
    b = _to_years(groups["b"], unit) if groups.get("b") else None
    plus = "+" in m.group(0) or "more" in m.group(0).lower() or bool(_AT_LEAST.search(before))
    if a is None:  # "up to 2 years"
        lo, hi = 0.0, b
    elif b is not None:  # range
        lo, hi = a, b
    else:
        lo, hi = a, (None if plus else a)
    return YoeMention(min_years=lo, max_years=hi, required=not preferred, evidence=evidence.strip())
