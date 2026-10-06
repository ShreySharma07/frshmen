"""Map a posting's free-text location (plus any ATS country code) to countries.

"Bangalore, Karnataka", "San Francisco, CA; New York, NY" and "Remote - US" all
become a clean country list for the page's country filter. Remote with no
country stays visible as "Remote (unspecified)" rather than being dropped.
Aliases live in config/locations.yaml.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "locations.yaml"
REMOTE_UNSPECIFIED = "Remote (unspecified)"
_REMOTE = re.compile(r"\bremote\b|\banywhere\b|\bwork from home\b|\bwfh\b", re.I)
_CODE_AFTER_COMMA = re.compile(r",\s*([A-Z]{2,3})\b")
# "us" is an English word, so only the uppercase standalone token counts ("Remote - US").
_US_UPPER = re.compile(r"(?<![\w.])US(?![\w])")


@dataclass
class Location:
    countries: list[str]
    remote: bool
    evidence: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class _Aliases:
    patterns: tuple[tuple[re.Pattern[str], str], ...]
    us_states: frozenset[str]
    iso: dict[str, str]


@lru_cache(maxsize=2)
def _load(path: Path = CONFIG) -> _Aliases:
    raw = yaml.safe_load(Path(path).read_text())
    pairs = [(alias.lower(), country) for country, aliases in raw["countries"].items() for alias in aliases]
    # Longest first so "new york city" wins over "new york", "delhi ncr" over "delhi".
    pairs.sort(key=lambda p: -len(p[0]))
    patterns = tuple((re.compile(rf"(?<![\w.]){re.escape(a)}(?![\w])", re.I), c) for a, c in pairs)
    return _Aliases(patterns, frozenset(raw["us_states"]), {k.upper(): v for k, v in raw["iso_codes"].items()})


def extract_location(location_raw: str | None, ats_countries: list[str] | None = None,
                     config: Path = CONFIG) -> Location:
    aliases = _load(config)
    text = (location_raw or "").strip()
    hits: dict[str, int] = {}  # country -> first position in the text, for display order

    def add(country: str, pos: int) -> None:
        hits[country] = min(pos, hits.get(country, pos))

    for code in ats_countries or []:
        country = aliases.iso.get(code.strip().upper()) or (code.strip() if len(code.strip()) > 3 else None)
        if country:
            add(country, -1)  # the ATS's structured field leads

    for m in _CODE_AFTER_COMMA.finditer(text):
        code = m.group(1)
        if code in aliases.us_states:
            add("United States", m.start())
        elif code in aliases.iso:
            add(aliases.iso[code], m.start())

    for m in _US_UPPER.finditer(text):
        add("United States", m.start())

    for pattern, country in aliases.patterns:
        m = pattern.search(text)
        if m:
            add(country, m.start())

    found = sorted(hits, key=hits.__getitem__)
    remote = bool(_REMOTE.search(text))
    countries = found or ([REMOTE_UNSPECIFIED] if remote else [])
    evidence = [{"kind": "location", "snippet": text}] if text else []
    if ats_countries:
        evidence.append({"kind": "ats_country", "snippet": ", ".join(ats_countries)})
    return Location(countries=countries, remote=remote, evidence=evidence)
