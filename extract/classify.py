"""Decide fresher / maybe / experienced for one posting (skills.md §2 decision table).

Precision over recall: a missed fresher job is acceptable, a 3-YoE job labelled
fresher is a bug. So any required 2+ years, or a senior title, wins over every
fresher signal, and anything unclear lands in `maybe`, never in `fresher`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from extract.sections import clauses
from extract.signals import batch_years, fresher_signals, senior_title
from extract.yoe import YoeMention, find_mentions

EXACT_BATCH = {2026}
SOFT_BATCH = {2025, 2027}


@dataclass
class Classification:
    level: str  # "fresher" | "maybe" | "experienced"
    level_confidence: float
    reason: str
    yoe_min: float | None = None
    yoe_max: float | None = None
    yoe_evidence: str | None = None
    batch_years: list[int] = field(default_factory=list)
    # Every snippet that influenced the decision, so a wrong label can be debugged.
    evidence: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify(title: str, description: str, exact_batch: set[int] = EXACT_BATCH,
             soft_batch: set[int] = SOFT_BATCH) -> Classification:
    parts = clauses(description)
    mentions = find_mentions(parts)
    required = [m for m in mentions if m.required]
    preferred = [m for m in mentions if not m.required]
    fresh = fresher_signals(title, parts)
    years, batch_ev = batch_years(parts)
    senior = senior_title(title)

    evidence = [{"kind": "yoe_required" if m.required else "yoe_preferred", "snippet": m.evidence} for m in mentions]
    evidence += [{"kind": s.kind, "snippet": s.evidence} for s in [*fresh, *batch_ev]]
    if senior:
        evidence.append({"kind": senior.kind, "snippet": senior.evidence})

    top = max(required, key=lambda m: m.min_years, default=None)
    base = dict(
        yoe_min=top.min_years if top else None,
        yoe_max=top.max_years if top else None,
        yoe_evidence=top.evidence if top else None,
        batch_years=years,
        evidence=evidence,
    )

    def result(level: str, conf: float, reason: str) -> Classification:
        return Classification(level=level, level_confidence=round(max(0.05, min(conf, 0.99)), 2), reason=reason, **base)

    # 1. Hard rejections.
    if senior:
        return result("experienced", 0.9, f"senior title: {title!r}")
    if top and top.min_years >= 2:
        return result("experienced", 0.95, f"requires {_fmt(top)} years")

    # 2. Batch targeting another year is a different audience, not a fresher match for Shrey.
    batch_ok = not years or bool(set(years) & (exact_batch | soft_batch))
    if not batch_ok:
        return result("maybe", 0.5, f"targets batch {years}, not {sorted(exact_batch | soft_batch)}")

    # 3. A requirement of 1+ years (open-ended) or a range past 1 year conflicts with "fresher".
    conflicting = [m for m in required if m.min_years >= 1 and (m.max_years is None or m.max_years > 1)]
    if conflicting:
        return result("maybe", 0.5, f"requires {_fmt(conflicting[0])} years")

    small_required = bool(required) and all(m.max_years is not None and m.max_years <= 1 for m in required)
    if not (fresh or small_required or (years and batch_ok)):
        reason = "no experience requirement or fresher signal found" if not mentions else "only preferred experience stated"
        return result("maybe", 0.5, reason)

    # 4. Fresher. Lower confidence for each softening factor.
    conf = 0.9 if (fresh or years) else 0.8
    notes = []
    if any(m.min_years >= 2 for m in preferred):
        conf -= 0.2
        notes.append("2+ years preferred")
    if years and not set(years) & exact_batch:
        conf -= 0.15
        notes.append(f"soft batch match {years}")
    why = "fresher signal" if fresh else ("batch year" if years else f"requires at most {_fmt(top)} years")
    return result("fresher", conf, why + (f" ({'; '.join(notes)})" if notes else ""))


def _fmt(m: YoeMention) -> str:
    lo = f"{m.min_years:g}"
    if m.max_years is None:
        return f"{lo}+"
    return lo if m.max_years == m.min_years else f"{lo}-{m.max_years:g}"
