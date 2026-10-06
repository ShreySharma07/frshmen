"""Map a posting's free-text location (plus any ATS country code) to countries.

"Bangalore, Karnataka", "San Francisco, CA; New York, NY" and "Remote - US" all
become a clean country list for the page's country filter, and Indian cities
("Bangalore" -> Bengaluru) for its City filter. Remote with no country stays
visible as "Remote (unspecified)" rather than being dropped.
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
    cities: list[str] = field(default_factory=list)  # Indian cities only, canonical names
    evidence: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class _Aliases:
    patterns: tuple[tuple[re.Pattern[str], str], ...]
    city_patterns: tuple[tuple[re.Pattern[str], str], ...]
    us_states: frozenset[str]
    iso: dict[str, str]


@lru_cache(maxsize=2)
def _load(path: Path = CONFIG) -> _Aliases:
    raw = yaml.safe_load(Path(path).read_text())
    cities = [(alias.lower(), city) for city, aliases in raw.get("india_cities", {}).items() for alias in aliases]
    pairs = [(alias.lower(), country) for country, aliases in raw["countries"].items() for alias in aliases]
    pairs += [(alias, "India") for alias, _ in cities]
    return _Aliases(_compile(pairs), _compile(cities), frozenset(raw["us_states"]),
                    {k.upper(): v for k, v in raw["iso_codes"].items()})


def _compile(pairs: list[tuple[str, str]]) -> tuple[tuple[re.Pattern[str], str], ...]:
    # Longest first so "new york city" wins over "new york", "navi mumbai" over "mumbai".
    pairs = sorted(pairs, key=lambda p: -len(p[0]))
    return tuple((re.compile(rf"(?<![\w.]){re.escape(a)}(?![\w])", re.I), name) for a, name in pairs)


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
    city_hits: dict[str, int] = {}
    taken: list[tuple[int, int]] = []  # a longer alias owns its span: "Delhi NCR" is not also "Delhi"
    for pattern, city in aliases.city_patterns:
        for m in pattern.finditer(text):
            if any(s < m.end() and m.start() < e for s, e in taken):
                continue
            taken.append(m.span())
            city_hits[city] = min(m.start(), city_hits.get(city, m.start()))
    cities = sorted(city_hits, key=city_hits.__getitem__)
    remote = bool(_REMOTE.search(text))
    countries = found or ([REMOTE_UNSPECIFIED] if remote else [])
    evidence = [{"kind": "location", "snippet": text}] if text else []
    if ats_countries:
        evidence.append({"kind": "ats_country", "snippet": ", ".join(ats_countries)})
    return Location(countries=countries, remote=remote, cities=cities, evidence=evidence)
