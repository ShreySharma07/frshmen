"""Polite HTTP client shared by the source adapters and the board verifier.

Good-citizen rules from CLAUDE.md live here so no adapter can skip them:
identify the bot, space out requests per host, back off when told to, and
send ETag / If-Modified-Since so unchanged boards cost the host almost nothing.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

USER_AGENT = "frshmen-jobboard/0.1 (personal job board; +https://github.com/ShreySharma07/frshmen)"
MIN_SECONDS_PER_HOST = 2.0
# Workable throttles far harder than the others (429 with Retry-After: 0).
HOST_INTERVAL = {"apply.workable.com": 5.0, "jobs.zs.com": 5.0}  # ZS: robots.txt crawl-delay 5
MAX_RETRIES = 4
RETRY_STATUSES = (429, 500, 502, 503, 504)
NOT_FOUND_STATUSES = (400, 404, 410)


class FetchError(RuntimeError):
    """A host never gave a usable answer after retries."""


@dataclass
class HttpClient:
    """GET JSON politely. `cache_dir` enables conditional requests across runs."""

    cache_dir: Path | None = None
    # Discovery (scripts/detect_careers.py) visits many unknown sites; dead ones must fail fast.
    retries: int = MAX_RETRIES
    timeout: float = 30.0
    last_hit: dict[str, float] = field(default_factory=dict)
    # Boards are fetched from several threads; pacing must still hold per host across all of them.
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def get_json(self, url: str, fresh_days: float | None = None) -> Any | None:
        """Parsed JSON, or None if the resource doesn't exist. Raises FetchError otherwise.

        `fresh_days`: reuse a stored copy younger than this without asking the host at all.
        For per-job detail calls, whose text rarely changes, so only new jobs cost a request.
        """
        return self._get(url, "application/json", json.loads, fresh_days)

    def get_text(self, url: str, accept: str = "text/html,application/xml;q=0.9,*/*;q=0.8",
                 fresh_days: float | None = None) -> str | None:
        """Body as text (careers pages, sitemaps), or None if it doesn't exist."""
        return self._get(url, accept, lambda raw: raw, fresh_days)

    def get_page(self, url: str) -> tuple[str, str] | None:
        """(final URL after redirects, HTML) for a web page, or None if it doesn't exist.

        For finding where a company's careers page really lives: "/careers" often redirects to
        the hiring system (e.g. acme.wd3.myworkdayjobs.com). Never cached.
        """
        return self._get(url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8", lambda raw: raw, with_url=True)

    def post_json(self, url: str, body: Any) -> Any | None:
        """POST a JSON body and parse the JSON answer (search endpoints careers sites call themselves).

        Same pacing, backoff and User-Agent as GET; never cached, since the answer depends on the body.
        """
        return self._get(url, "application/json", json.loads, data=json.dumps(body).encode())

    def _get(self, url: str, accept: str, decode: Callable[[str], Any], fresh_days: float | None = None,
             data: bytes | None = None, with_url: bool = False) -> Any | None:
        host = urlparse(url).netloc
        cached = self._cache_read(url) if data is None and not with_url else None
        if fresh_days and cached and time.time() - cached.get("stored_at", 0) < fresh_days * 86400:
            return cached["body"]
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "en-US,en;q=0.8"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if cached:
            if cached.get("etag"):
                headers["If-None-Match"] = cached["etag"]
            if cached.get("last_modified"):
                headers["If-Modified-Since"] = cached["last_modified"]
        req = urllib.request.Request(url, headers=headers, data=data, method="POST" if data is not None else "GET")

        for attempt in range(self.retries + 1):
            self._pace(host)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    body = decode(raw)
                    if with_url:
                        return resp.geturl(), body
                    if data is None:
                        self._cache_write(url, resp.headers.get("ETag"), resp.headers.get("Last-Modified"), body,
                                          keep=bool(fresh_days))
                    return body
            except urllib.error.HTTPError as e:
                if e.code == 304 and cached:
                    return cached["body"]
                if e.code in NOT_FOUND_STATUSES:
                    return None
                if e.code not in RETRY_STATUSES or attempt == self.retries:
                    raise FetchError(f"{host}: HTTP {e.code}") from e
                self._back_off(host, attempt, e.headers.get("Retry-After"))
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == self.retries:
                    raise FetchError(f"{host}: {e}") from e
                self._back_off(host, attempt, None)
            except json.JSONDecodeError:
                return None
        return None

    def _pace(self, host: str) -> None:
        interval = HOST_INTERVAL.get(host, MIN_SECONDS_PER_HOST)
        # Reserve the next slot for this host under the lock, then sleep outside it.
        with self._lock:
            now = time.monotonic()
            slot = max(now, self.last_hit.get(host, 0.0) + interval) if host in self.last_hit else now
            self.last_hit[host] = slot
        if slot > now:
            time.sleep(slot - now)

    def _back_off(self, host: str, attempt: int, retry_after: str | None) -> None:
        # Exponential 5s, 10s, 20s, 40s, raised to the server's Retry-After when larger
        # (some hosts send Retry-After: 0, which would mean hammering them).
        delay = 5.0 * 2**attempt
        if retry_after and retry_after.isdigit():
            delay = max(delay, float(retry_after))
        delay = min(delay, 60.0)
        print(f"  {host} asked us to slow down; waiting {delay:.0f}s", file=sys.stderr, flush=True)
        time.sleep(delay)
        self.last_hit[host] = time.monotonic()

    # --- conditional-request cache -------------------------------------------------

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"

    def _cache_read(self, url: str) -> dict[str, Any] | None:
        path = self._cache_path(url)
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def _cache_write(self, url: str, etag: str | None, last_modified: str | None, body: Any,
                     keep: bool = False) -> None:
        path = self._cache_path(url)
        # Worth storing when the host gave us something to revalidate with, or the caller reuses it by age.
        if path is None or not (etag or last_modified or keep):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"url": url, "etag": etag, "last_modified": last_modified, "body": body,
                                    "stored_at": time.time()}))
