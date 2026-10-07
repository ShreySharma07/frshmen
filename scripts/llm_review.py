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
# Newest stable Flash-Lite first. Google stops serving older models to new keys before their
# listed shutdown (2.5 Flash-Lite answered 404 on 2026-10-07), so a 404 moves to the next.
MODELS = [m for m in [os.environ.get("GEMINI_MODEL", "")] if m] or [
    "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_CALLS = 100
PACE_SECONDS = 4.5
# Same window the API uses for what the page lists (api/src/jobs_api.py MAX_POST_AGE_DAYS).
MAX_POST_AGE_DAYS = 30
# Consecutive failed calls (not rejected answers) before the run stops asking.
MAX_FAILURES = 3


class QuotaExhausted(RuntimeError):
    """Rate or daily limit hit, or the key was refused: stop asking this run."""


class CallFailed(RuntimeError):
    """The model gave no answer (HTTP error, network, empty reply). Never cached: retried next run."""


def _error_detail(e: urllib.error.HTTPError) -> str:
    try:
        return json.loads(e.read().decode())["error"]["message"][:200]
    except Exception:
        return ""


def gemini_call(api_key: str, models: list[str] | None = None):
    """A ModelCall that posts to Gemini with JSON-schema output. The key goes in a header, never the URL."""
    last = [0.0]
    remaining = list(models or MODELS)

    def call(prompt: str, schema: dict[str, Any]) -> Any:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                 "responseSchema": schema},
        }
        while remaining:
            wait = PACE_SECONDS - (time.monotonic() - last[0])
            if wait > 0:
                time.sleep(wait)
            last[0] = time.monotonic()
            req = urllib.request.Request(
                ENDPOINT.format(model=remaining[0]), data=json.dumps(body).encode(), method="POST",
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.load(resp)
            except urllib.error.HTTPError as e:
                detail = _error_detail(e)
                if e.code == 404:
                    print(f"  {remaining.pop(0)} not available ({detail}); trying the next model", file=sys.stderr)
                    continue
                if e.code in (429, 403):
                    raise QuotaExhausted(f"HTTP {e.code} {detail}") from None
                raise CallFailed(f"HTTP {e.code} {detail}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                raise CallFailed(f"unreachable ({e})") from None
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, TypeError):
                raise CallFailed("empty or blocked answer") from None
        raise QuotaExhausted("no Gemini model available to this key")

    call.models = remaining  # type: ignore[attr-defined]  # for the run summary
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
    stats = {"candidates": 0, "cached": 0, "asked": 0, "failed": 0, "accepted": 0, "changed_level": 0}
    # Newest first, so a capped run spends its requests on what the page shows at the top.
    order = sorted(range(len(records)), key=lambda i: records[i].get("posted_at") or records[i].get("first_seen_at") or "",
                   reverse=True)
    out = list(records)
    quota_left = True
    failures = 0
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
                print(f"Gemini stopped ({e}); remaining jobs wait for the next run.", file=sys.stderr)
                quota_left = False
                continue
            except CallFailed as e:
                stats["failed"] += 1
                failures += 1
                print(f"  {rec.get('id')}: {e}", file=sys.stderr)
                if failures >= MAX_FAILURES:
                    print(f"{failures} failed calls in a row; stopping this run's reviews.", file=sys.stderr)
                    quota_left = False
                continue
            failures = 0
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
    model = (getattr(call, "models", None) or ["none"])[0]
    print(f"LLM review ({model}): {stats['candidates']} maybe jobs shown, {stats['cached']} cached, "
          f"{stats['asked']} answered, {stats['failed']} failed, {stats['accepted']} accepted, "
          f"{stats['changed_level']} changed level")
    return 0


if __name__ == "__main__":
    sys.exit(main())
