"""What leaves for Gemini (docs/decisions.md, 2026-11-18, security review M4): a resume's email
addresses and phone numbers are replaced before any prompt, since Gemini's free tier may use what
it is sent. Judging fit or rewording a line never needs them.
"""

from __future__ import annotations

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# A run of digits with the usual separators. Counted as a phone only with 10 to 15 digits, so years
# ("2022 - 2026"), dates and scores stay.
_DIGITS = re.compile(r"(?<![\w/])\+?\(?\d[\d\s().-]{6,}\d(?![\w/])")
EMAIL_MARK, PHONE_MARK = "[email]", "[phone]"


def _phone(m: re.Match[str]) -> str:
    n = sum(c.isdigit() for c in m.group())
    return PHONE_MARK if 10 <= n <= 15 else m.group()


def redact(text: str) -> str:
    return _DIGITS.sub(_phone, EMAIL.sub(EMAIL_MARK, text or ""))


def redacted(text: str) -> bool:
    return EMAIL_MARK in text or PHONE_MARK in text
