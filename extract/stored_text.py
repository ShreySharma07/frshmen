"""Keep only the parts of a posting a candidate needs: about the role, required, preferred.

Decided 2026-10-18 (docs/strategy/company-coverage.md): the database stores these three sections,
not the whole description, to stay inside Supabase's 500 MB. Extractors read the full text first
(YoE, role, visa, location) and keep their own evidence, so nothing they need is lost here.

Postings mark sections with short heading lines ("What you'll do", "Nice to haves"). Headings are
matched against the phrases real postings use (surveyed on 488 stored jobs, 2026-10-19); company
blurbs, benefits, pay bands, EEO and privacy notices are dropped. A posting with no recognisable
heading keeps its opening as "About the role". As in extract/sections.py, "Ideally you'd have" is
required, not preferred: Scale AI uses it for the main requirements.
"""

from __future__ import annotations

import re

LIMITS = {"about": 1500, "required": 2000, "preferred": 1000}  # characters per section
TITLES = {"about": "About the role", "required": "Required", "preferred": "Preferred"}

_ABOUT = re.compile(
    r"^(about (the|this) (role|position|job|opportunity|team)|the (role|opportunity|position)|role (summary|overview)|"
    r"job (description|summary|overview)|position (summary|overview)|overview|your (role|impact|mission)|"
    r"(key )?responsibilities|(what|how) you('ll| will) (do|build|work on|contribute)|what will you (do|build)|"
    r"in this role,? you( will|'ll)?|you will|day[- ]to[- ]day|what (the|this) role (is|involves))\b", re.I)
_PREFERRED = re.compile(
    r"^(preferred( qualifications| skills| experience)?|nice[- ]to[- ]haves?|good[- ]to[- ]have|bonus( points)?|"
    r"it'?s a plus|pluses|extra credit|desired( qualifications| skills)?|you'?ll stand out)\b", re.I)
_REQUIRED = re.compile(
    r"^((minimum|basic|required|must[- ]have|key|essential) (qualifications|requirements|skills)|requirements|"
    r"qualifications|required|must[- ]haves?|what (you('ll)? need|we('re| are)? look(ing)? for|you bring|you'll bring)|"
    r"what will you need|who you are|about you|who should apply|you (may be a good fit|might thrive|should have|have)|"
    r"skills( and| &) (experience|qualifications)|experience( required)?|signals we look for|your (background|profile|skills)|"
    r"ideally,? you('d| would| will)? have)\b",
    re.I)
# Everything else a posting adds around the job itself.
_DROP = re.compile(
    r"^(about (us|[\w&.' -]{2,30})$|why (join|work|us)|our (mission|values|culture|story)|benefits|perks|"
    r"compensation|salary|pay|location|equal opportunity|eeo|diversity|privacy|how to apply|application|"
    r"culture|life at|what we offer|we offer|#li-|\$)", re.I)


def _heading(line: str) -> str | None:
    """The heading text if the line is one: short, no sentence ending, optionally ending in ':'."""
    text = line.strip().strip("*#").strip()
    if not text or len(text) > 60 or re.match(r"^[-•*]\s", line.strip()):
        return None
    text = text[:-1].strip() if text.endswith(":") else text
    if re.search(r"[.,;!]$", text):
        return None
    return text.replace("’", "'")


def split(text: str) -> dict[str, str]:
    """{"about", "required", "preferred"} -> section text (empty when the posting has none)."""
    parts: dict[str, list[str]] = {"about": [], "required": [], "preferred": []}
    intro: list[str] = []
    current: str | None = "intro"
    for line in (text or "").split("\n"):
        heading = _heading(line)
        if heading is not None:
            kind = ("preferred" if _PREFERRED.match(heading) else "required" if _REQUIRED.match(heading)
                    else "about" if _ABOUT.match(heading) else "drop" if _DROP.match(heading) else None)
            if kind == "drop":
                current = None
                continue
            if kind is not None:
                current = kind
                continue
            # An unknown short line is a sub-heading inside the current section ("Technical skills").
        if current == "intro":
            intro.append(line)
        elif current is not None:
            parts[current].append(line)
    if not any(parts.values()):
        parts["about"] = intro  # no recognisable sections: the opening is the best summary we have
    return {k: _clip("\n".join(v).strip(), LIMITS[k]) for k, v in parts.items()}


def compact(text: str, evidence: list[dict[str, str]] | None = None) -> str:
    """The stored description: the three sections under fixed headings, each within its limit.

    `evidence` is the classifier's snippets (extract/classify.py). Any that the sections lost
    (a YoE line under an unrecognised heading, or past a limit) is added back, so the label's
    reason always shows on the page: "yoe_preferred" under Preferred, the rest under Required.
    """
    sections = split(text)
    for item in evidence or []:
        snippet = (item.get("snippet") or "").strip()
        if not snippet or str(item.get("kind")).endswith("title") or snippet in sections["about"] \
                or snippet in sections["required"] or snippet in sections["preferred"]:
            continue
        key = "preferred" if item.get("kind") == "yoe_preferred" else "required"
        sections[key] = f"- {snippet}\n{sections[key]}".strip()
    # Clipped again after adding evidence (which goes first, so it survives): one pass gives the
    # final text, and compacting stored text changes nothing.
    sections = {k: _clip(body, LIMITS[k]) for k, body in sections.items()}
    return "\n\n".join(f"{TITLES[k]}\n{body}" for k, body in sections.items() if body)


def _clip(text: str, limit: int) -> str:
    """Cut at the last whole line within the limit; a single long line is cut at a word."""
    if len(text) <= limit:
        return text
    room = limit - 2  # for " …", so a clipped section is never clipped again
    cut = text.rfind("\n", 0, room)
    if cut < room // 2:
        cut = text.rfind(" ", 0, room)
    return text[:cut].rstrip() + " …"
