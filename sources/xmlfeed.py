"""Tiny helpers for the RSS/XML job feeds (Teamtailor, JazzHR): flat records, read with regexes.

The feeds are shallow and machine-written, so a regex per tag is enough, and it avoids feeding
untrusted XML to a full parser (entity expansion) for no gain.
"""

from __future__ import annotations

import re
from html import unescape


def records(xml: str, tag: str) -> list[str]:
    return re.findall(rf"<{tag}>(.*?)</{tag}>", xml or "", re.S)


def field(record: str, tag: str) -> str:
    """The first <tag>'s text: CDATA kept as is, escaped text unescaped. "" when absent or empty."""
    m = re.search(rf"<{re.escape(tag)}(?:\s[^>]*)?>(.*?)</{re.escape(tag)}>", record, re.S)
    if not m:
        return ""
    value = m.group(1).strip()
    cdata = re.fullmatch(r"<!\[CDATA\[(.*?)\]\]>", value, re.S)
    return cdata.group(1).strip() if cdata else unescape(value)
