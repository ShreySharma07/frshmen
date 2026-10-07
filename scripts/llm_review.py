"""Ask Gemini about the `maybe` jobs the page would show, and fold accepted answers into data/jobs.json.

Runs between fetch_jobs.py and publish_d1.py. Without GEMINI_API_KEY it does nothing,
so the pipeline stays rules-only. Verdicts are cached by content_hash (and PROMPT_VERSION),
so each posting costs one request ever; the cache lives in .cache/llm between runs.

Free tier (Gemini API, checked 2026-10-07; Google changes these without notice): about
15 requests/minute and 1,000/day for Flash-Lite, prompts may be used to improve Google's
products (postings are public). We stay under both: MAX_CALLS per run x 8 runs a day,
one request every PACE_SECONDS, and the first 429 ends the run's reviews.

Run: python scripts/llm_review.py [--jobs data/jobs.json] [--max-calls N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extract import llm  # noqa: E402

JOBS = ROOT / "data" / "jobs.json"
CACHE = ROOT / ".cache" / "llm" / "verdicts.json"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_CALLS = 100
PACE_SECONDS = 4.5
# Same window the API uses for what the page lists (api/src/jobs_api.py MAX_POST_AGE_DAYS).
MAX_POST_AGE_DAYS = 30


class QuotaExhausted(RuntimeError):
    pass


def gemini_call(api_key: str, model: str = MODEL):
    """A ModelCall that posts to Gemini with JSON-schema output. The key goes in a header, never the URL."""
    last = [0.0]

    def call(prompt: str, schema: dict[str, Any]) -> Any:
        wait = PACE_SECONDS - (time.monotonic() - last[0])
        if wait > 0:
            time.sleep(wait)
        last[0] = time.monotonic()
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                 "responseSchema": schema},
        }
        req = urllib.request.Request(
            ENDPOINT.format(model=model), data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 403):
                raise QuotaExhausted(f"HTTP {e.code}") from None
            print(f"  Gemini HTTP {e.code}; skipped", file=sys.stderr)
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  Gemini unreachable ({e}); skipped", file=sys.stderr)
            return None
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return None  # blocked or empty answer

    return call


def shown(record: dict[str, Any], now: datetime) -> bool:
    """Would the page list this job? Only those are worth a request."""
    if not (record.get("role_match") and record.get("eligible")):
        return False
    posted = record.get("posted_at")
    if not posted:
        return True
    try:
        when = datetime.fromisoformat(posted.replace("Z", "+00:00"))
    except ValueError:
        return True
    return now - when <= timedelta(days=MAX_POST_AGE_DAYS)


def cache_key(record: dict[str, Any]) -> str:
    return f"v{llm.PROMPT_VERSION}:{record['content_hash']}"


def load_cache(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def run(records: list[dict[str, Any]], call, cache: dict[str, Any], max_calls: int,
        now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Records with verdicts applied, plus counts. Cached verdicts (including "no usable answer") are reused."""
    now = now or datetime.now(timezone.utc)
    stats = {"candidates": 0, "cached": 0, "asked": 0, "accepted": 0, "changed_level": 0}
    # Newest first, so a capped run spends its requests on what the page shows at the top.
    order = sorted(range(len(records)), key=lambda i: records[i].get("posted_at") or records[i].get("first_seen_at") or "",
                   reverse=True)
    out = list(records)
    quota_left = True
    for i in order:
        rec = records[i]
        if not (llm.needs_review(rec) and shown(rec, now)):
            continue
        stats["candidates"] += 1
        key = cache_key(rec)
        if key in cache:
            stats["cached"] += 1
            raw = cache[key]
        elif quota_left and stats["asked"] < max_calls:
            try:
                verdict = llm.review(rec, call)
            except QuotaExhausted as e:
                print(f"Gemini quota reached ({e}); remaining jobs wait for the next run.", file=sys.stderr)
                quota_left = False
                continue
            stats["asked"] += 1
            raw = verdict.__dict__ if verdict else None
            cache[key] = raw
        else:
            continue
        if raw is None:
            continue
        stats["accepted"] += 1
        updated = llm.apply(rec, llm.Verdict(**raw))
        stats["changed_level"] += updated["level"] != rec["level"]
        out[i] = updated
    return out, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=Path, default=JOBS)
    parser.add_argument("--cache", type=Path, default=CACHE)
    parser.add_argument("--max-calls", type=int, default=MAX_CALLS)
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    payload = json.loads(args.jobs.read_text())
    cache = load_cache(args.cache)
    call = gemini_call(api_key) if api_key else (lambda prompt, schema: None)
    # Without a key only cached verdicts are applied, so labels don't flip back when the secret is missing.
    records, stats = run(payload["jobs"], call, cache, args.max_calls if api_key else 0)
    payload["jobs"] = records
    args.jobs.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_text(json.dumps(cache))
    if not api_key:
        print("GEMINI_API_KEY not set: applied cached verdicts only.")
    print(f"LLM review ({MODEL}): {stats['candidates']} maybe jobs shown, {stats['cached']} cached, "
          f"{stats['asked']} asked, {stats['accepted']} accepted, {stats['changed_level']} changed level")
    return 0


if __name__ == "__main__":
    sys.exit(main())
