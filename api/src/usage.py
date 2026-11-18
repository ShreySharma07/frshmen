"""Daily limits, counted per person (docs/decisions.md, 2026-11-18, security H1).

A use (agent message, fit check, tailored resume, email reveal) is a row in usage_events under
`who`, a keyed hash of the person's normalised email, so deleting the profile, or the account, and
signing up again with the same address doesn't reset it. Counting and recording happen under a
per-person transaction lock, so requests sent at once count one after the other.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime

from storage import Database

WINDOW = "interval '24 hours'"
KEEP = "interval '48 hours'"  # only the last 24 hours count; a day's margin, then they go
KINDS = ("agent_message", "fit_check", "tailor", "contact_reveal")
# Gmail ignores dots in the name, and many providers ignore "+tag": one inbox, one person.
DOTLESS = {"gmail.com", "googlemail.com"}


def normalise(email: str) -> str:
    name, _, domain = email.strip().lower().partition("@")
    name = name.split("+", 1)[0]
    if domain in DOTLESS:
        name, domain = name.replace(".", ""), "gmail.com"
    return f"{name}@{domain}"


def who(uid: str, email: str | None, key: str = "") -> str:
    """The person a use is counted against. Keyed (Worker secret USAGE_HASH_KEY) so the stored hash
    can't be matched to an email by hashing guesses; without a key, a plain SHA-256."""
    subject = f"email:{normalise(email)}" if email and "@" in email else f"user:{uid}"
    if key:
        return hmac.new(key.encode(), subject.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(subject.encode()).hexdigest()


async def lock(db: Database, person: str) -> None:
    """Serialise one person's counting until the transaction ends (call inside db.transaction())."""
    await db.all("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", [person])


async def used(db: Database, person: str, kind: str) -> tuple[int, datetime | None]:
    """(uses in the last 24 hours, when the oldest of them stops counting)."""
    row = (await db.all(f"SELECT COUNT(*) AS n, MIN(created_at) + {WINDOW} AS frees FROM usage_events "
                        f"WHERE who = $1 AND kind = $2 AND created_at > now() - {WINDOW}", [person, kind]))[0]
    return int(row["n"]), row["frees"]


async def record(db: Database, person: str, kind: str) -> int:
    # Old rows go a few at a time, so no request pays for a big delete.
    await db.all(f"DELETE FROM usage_events WHERE id IN (SELECT id FROM usage_events WHERE created_at < now() - {KEEP} LIMIT 50)")
    return (await db.all("INSERT INTO usage_events (who, kind) VALUES ($1, $2) RETURNING id", [person, kind]))[0]["id"]


async def forget(db: Database, event_id: int) -> None:
    """A use that failed on Google's side doesn't count."""
    await db.all("DELETE FROM usage_events WHERE id = $1", [event_id])
