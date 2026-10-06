"""Fresher signals, batch years and senior-title checks, each with its evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from extract.sections import Clause

# Phrases in the description that mean "this is for people starting out".
# Bare "graduate(s)" is not enough: "MBA graduates with 1-2 years" is not a new-grad role.
_FRESHER_TEXT = re.compile(
    r"\bnew[- ]grad(uate)?s?\b|\brecent[- ]grad(uate)?s?\b|"
    # "fresher" as a noun ("Freshers can apply"), never the adjective "fresh" or "fresher ideas".
    r"\bfreshers?\b(?![- ]?(?:look|eyes|ideas|perspective|produce|food|data|content))|\bfresh graduates?\b|"
    r"\bentry[- ]level\b|\bcampus (hire|hiring|recruit\w*|placement)s?\b|\bearly[- ]career\b|"
    r"\bgraduate (program(me)?|role|scheme|engineer|trainee)\b|\bfinal[- ]year students?\b|"
    r"\bno (prior )?(work )?experience (is )?(required|needed|necessary)\b|\b0\s*(?:-|–|to)\s*1\s*(?:years?|yrs?)\b|"
    r"\bclass of 20\d\d\b|\b20\d\d\s*batch\b|\bbatch of 20\d\d\b",
    re.I,
)
_FRESHER_TITLE = re.compile(
    r"\bnew[- ]grad(uate)?\b|\bgraduate\b|\btrainee\b|\bfresher\b|\bentry[- ]level\b|\bearly[- ]career\b|"
    r"\bcampus\b|\bapprentice\b|\buniversity (grad|hire)\b",
    re.I,
)
# Seniority in the title outranks everything in the text. "Assistant/Associate Manager"
# and "Associate Product Manager" are common entry-level titles, so they don't count.
_SENIOR_TITLE = re.compile(
    r"\b(senior|sr\.?|staff|lead|principal|director|head of|vp|vice president|chief|architect|distinguished)\b|"
    r"\b(iii|iv|v)\b\s*$",
    re.I,
)
_MANAGER = re.compile(r"\bmanager\b", re.I)
_JUNIOR_MANAGER = re.compile(r"\b(assistant|associate)\b[^,|/-]*\bmanager\b", re.I)
_BATCH_CONTEXT = re.compile(r"graduat|\bbatch\b|class of|pass(ing|ed)?[- ]?out|degree completion|final[- ]year", re.I)
_YEAR = re.compile(r"\b(20[2-3]\d)\b")


@dataclass(frozen=True)
class Signal:
    kind: str  # "fresher_text" | "fresher_title" | "senior_title" | "batch"
    evidence: str


def senior_title(title: str) -> Signal | None:
    if _SENIOR_TITLE.search(title) or (_MANAGER.search(title) and not _JUNIOR_MANAGER.search(title)):
        return Signal("senior_title", title)
    return None


def fresher_signals(title: str, clauses: list[Clause]) -> list[Signal]:
    found = []
    if _FRESHER_TITLE.search(title):
        found.append(Signal("fresher_title", title))
    for clause in clauses:
        if _FRESHER_TEXT.search(clause.text):
            found.append(Signal("fresher_text", clause.text))
    return found


def batch_years(clauses: list[Clause]) -> tuple[list[int], list[Signal]]:
    """Graduation years the posting targets, e.g. "2025/2026 batch" or "graduating Fall 2026 or Spring 2027"."""
    years: set[int] = set()
    evidence = []
    for clause in clauses:
        if not _BATCH_CONTEXT.search(clause.text):
            continue
        hits = {int(y) for y in _YEAR.findall(clause.text)}
        if hits:
            years |= hits
            evidence.append(Signal("batch", clause.text))
    return sorted(years), evidence
