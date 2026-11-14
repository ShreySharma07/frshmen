"""Shrey's HR and YC founder lists, as CSV text, into contact rows (db/postgres/0013_contacts.sql).

Forgiving about the header (exports say "Full Name", "Designation", "Organisation", "Mobile"...),
strict about values: a row without a name or company, or with a malformed email, is refused with
its row number and the reason, never half-imported.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

# Our column -> header names seen in real exports (compared lowercase, spaces and _ ignored).
ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "full name", "contact name"),
    "company": ("company", "company name", "organisation", "organization", "startup", "employer"),
    "title": ("title", "designation", "role", "position", "job title"),
    "email": ("email", "email id", "email address", "e-mail", "mail"),
    "phone": ("phone", "mobile", "phone number", "mobile number", "contact number", "contact"),
    "linkedin": ("linkedin", "linkedin url", "linkedin profile", "profile"),
    "location": ("location", "city"),
    "yc_batch": ("yc batch", "batch"),
    "company_url": ("company url", "website", "url", "company website"),
    "notes": ("notes", "note", "comments", "remarks"),
}
LIMITS = {"name": 120, "company": 120, "title": 160, "email": 254, "phone": 40, "linkedin": 300, "location": 120,
          "yc_batch": 12, "company_url": 300, "notes": 1000}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_ROWS = 5000


def _key(header: str) -> str:
    return re.sub(r"[\s_]+", " ", header.strip().lower())


def _columns(headers: list[str]) -> dict[str, str]:
    """Our column -> the file's header for it."""
    found = {}
    for col, names in ALIASES.items():
        for h in headers:
            if _key(h) in names:
                found[col] = h
                break
    return found


def parse(text: str, kind: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(rows ready to insert, refused rows as {row, reason}). Row numbers count the header as 1."""
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    cols = _columns(reader.fieldnames or [])
    for need in ("name", "company"):
        if need not in cols:
            return [], [{"row": 1, "reason": f"no {need} column (expected one of: {', '.join(ALIASES[need])})"}]

    rows, errors = [], []
    for n, raw in enumerate(reader, start=2):
        if n - 1 > MAX_ROWS:
            errors.append({"row": n, "reason": f"more than {MAX_ROWS} rows; split the file"})
            break
        value = {col: (raw.get(h) or "").strip()[: LIMITS[col]] or None for col, h in cols.items()}
        if not any(value.values()):
            continue  # blank line
        if not value.get("name"):
            errors.append({"row": n, "reason": "name is missing"})
            continue
        if not value.get("company"):
            errors.append({"row": n, "reason": "company is missing"})
            continue
        email = (value.get("email") or "").lower() or None
        if email and not EMAIL.match(email):
            errors.append({"row": n, "reason": f"email {value['email']!r} is not an address"})
            continue
        row = {"kind": kind, **{col: value.get(col) for col in ALIASES}, "email": email}
        for link in ("linkedin", "company_url"):
            if row[link] and not re.match(r"^https?://", row[link]):
                row[link] = None  # only web links, never javascript: or anything else
        rows.append(row)
    return rows, errors
