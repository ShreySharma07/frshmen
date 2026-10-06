"""Cheap title screen for ATSs that need one request per job to get its description.

Workday and Darwinbox list titles first and descriptions only per job. Fetching
a description for every sales or operations opening would multiply requests to
their hosts for jobs the role filter drops anyway, so those adapters only fetch
(and emit) jobs whose title could be a target role. Deliberately broad: the real
role decision stays in extract/role.py.
"""

from __future__ import annotations

import re

_MAYBE_TARGET = re.compile(
    r"engineer|developer|programmer|\bsde\b|scien|machine learning|\bml\b|\bai\b|\bllm|gen ?ai|data|"
    r"research|intern|graduate|trainee|fresher|analyst|python|back-?end|software|platform|mlops|"
    r"computer vision|\bnlp\b|deep learning",
    re.I,
)


def could_be_target(title: str) -> bool:
    return bool(_MAYBE_TARGET.search(title or ""))


def experience_line(text: str | None) -> str:
    """Render a structured experience field as a sentence the YoE extractor reads, keeping it as evidence.

    "3-5" -> "Experience: 3-5 years". Empty when the ATS gave nothing.
    """
    text = (text or "").strip()
    if not text or not re.search(r"\d", text):
        return ""
    return f"Experience: {text}" if re.search(r"year|yr", text, re.I) else f"Experience: {text} years"
