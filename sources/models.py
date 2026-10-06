"""Shapes shared by every source adapter.

Adapters only map an ATS payload onto `Job`. Anything that interprets text
(experience, location type, visa, skills) belongs in extract/, not here.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Company:
    name: str
    ats: str
    slug: str
    category: str = ""


@dataclass
class Job:
    source: str  # ATS name, e.g. "greenhouse"
    external_id: str  # the ATS's own id for the posting
    company: str
    company_slug: str
    title: str
    url: str
    location_raw: str
    description_text: str
    posted_at: str | None = None  # ISO 8601 UTC, only if the ATS gives one
    department: str | None = None
    employment_type: str | None = None
    # Structured hints straight from the ATS. Raw on purpose: extract/ decides
    # the final location_type/countries and keeps the evidence.
    ats_workplace_type: str | None = None
    ats_countries: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.company_slug}:{self.external_id}"

    @property
    def content_hash(self) -> str:
        """Changes when the posting text changes, which is what triggers re-extraction."""
        return _sha256("\x1f".join([self.title, self.location_raw, self.description_text]))

    @property
    def dedupe_key(self) -> str:
        """Catches the same role cross-posted under different ids."""
        parts = [self.company, self.title, self.location_raw, self.url.split("?")[0].rstrip("/")]
        return _sha256("\x1f".join(p.strip().lower() for p in parts))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, **asdict(self), "content_hash": self.content_hash}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
