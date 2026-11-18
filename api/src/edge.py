"""What runs before the API answers (docs/decisions.md, 2026-11-18, security review M2): a rate limit
per visitor, then a cache for the public pages' data.

Analogy: a shop's door. The rate limit is the doorman (one visitor can't walk in 1,000 times a
minute); the cache is a stack of today's paper by the door, so a crowd costs one print, not one each.

- Rate limit: Cloudflare's Workers rate-limiting binding, counted per visitor (their IP) in each
  Cloudflare location. Two budgets: API (every /api/ request) and AI (routes that call Gemini).
  It is the inner wall; a Cloudflare dashboard rule in front of the Worker is the outer one.
- Cache: anonymous GETs of the public routes are kept in Cloudflare's cache (the Workers Cache API)
  for CACHE_SECONDS. The answers change only when the pipeline publishes (every ~3 hours), so a few
  minutes old is fine. Anything with an Authorization header is never cached or served from cache.

Both sit behind small interfaces so tests (and local runs, where neither exists) use fakes or nothing.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

CACHE_SECONDS = 300
BROWSER_SECONDS = 60
# Public routes whose answer is the same for every anonymous visitor.
CACHEABLE = ("/api/jobs", "/api/meta", "/api/evidence", "/api/skill-demand")
# Routes that call Gemini: a much smaller budget per visitor, on top of each person's daily limit.
AI_ROUTE = re.compile(r"^/api/(agent/|jobs/.+/(fit|tailor)$)")


class Limiter(Protocol):
    async def allow(self, key: str) -> bool: ...


class Cache(Protocol):
    async def get(self, url: str) -> tuple[int, dict[str, str], bytes] | None: ...
    async def put(self, url: str, status: int, headers: dict[str, str], body: bytes) -> None: ...


class WorkerLimiter:
    """A rate-limiting binding (api/wrangler.jsonc "ratelimits"): limit({key}) -> {success}."""

    def __init__(self, binding: Any):
        self.binding = binding

    async def allow(self, key: str) -> bool:
        from js import Object  # type: ignore[import-not-found]
        from pyodide.ffi import to_js  # type: ignore[import-not-found]

        outcome = await self.binding.limit(to_js({"key": key}, dict_converter=Object.fromEntries))
        return bool(outcome.success)


class WorkerCache:
    """Cloudflare's cache in the Worker's data centre (caches.default), keyed by the full URL."""

    async def get(self, url: str) -> tuple[int, dict[str, str], bytes] | None:
        from js import caches  # type: ignore[import-not-found]

        hit = await caches.default.match(url)
        if hit is None:
            return None
        body = bytes((await hit.arrayBuffer()).to_py())
        return int(hit.status), {k: v for k, v in hit.headers.entries()}, body

    async def put(self, url: str, status: int, headers: dict[str, str], body: bytes) -> None:
        from js import Object, caches  # type: ignore[import-not-found]
        from js import Response as JsResponse
        from pyodide.ffi import to_js  # type: ignore[import-not-found]

        # to_js turns bytes into a Uint8Array, which a Response takes as its body.
        init = to_js({"status": status, "headers": headers}, dict_converter=Object.fromEntries)
        await caches.default.put(url, JsResponse.new(to_js(body), init))


def _visitor(request: Request) -> str:
    # Cloudflare sets CF-Connecting-IP to the visitor's address; anything else is a local run.
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "local")


def _limiters(request: Request) -> tuple[Limiter | None, Limiter | None]:
    test = getattr(request.app.state, "limiters", None)
    if test is not None:
        return test
    env = request.scope.get("env")
    api, ai = (getattr(env, "API_LIMITER", None), getattr(env, "AI_LIMITER", None)) if env is not None else (None, None)
    return (WorkerLimiter(api) if api else None, WorkerLimiter(ai) if ai else None)


def _cache(request: Request) -> Cache | None:
    test = getattr(request.app.state, "cache", None)
    if test is not None:
        return test
    return WorkerCache() if request.scope.get("env") is not None else None


def _too_many(what: str) -> JSONResponse:
    return JSONResponse({"detail": f"too many {what} from your connection; wait a minute and try again"},
                        status_code=429, headers={"Retry-After": "60"})


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def edge(request: Request, call_next: Any) -> Response:
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        # 1. The doorman: per visitor, before any database or Gemini work.
        api_limit, ai_limit = _limiters(request)
        visitor = _visitor(request)
        if api_limit and not await api_limit.allow(f"api:{visitor}"):
            return _too_many("requests")
        if ai_limit and request.method == "POST" and AI_ROUTE.match(path) and not await ai_limit.allow(f"ai:{visitor}"):
            return _too_many("AI requests")

        # 2. The stack of papers: only anonymous GETs of public routes.
        cache = _cache(request)
        public = (cache is not None and request.method == "GET" and path in CACHEABLE
                  and "authorization" not in request.headers)
        if not public:
            return await call_next(request)
        url = str(request.url)
        try:
            hit = await cache.get(url)
        except Exception:  # noqa: BLE001 - the cache is an optimisation; never fail a request on it
            hit = None
        if hit is not None:
            status, headers, body = hit
            return Response(content=body, status_code=status, headers={**headers, "x-aventra-cache": "hit"})

        response = await call_next(request)
        if response.status_code != 200:
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        headers = {"content-type": response.headers.get("content-type", "application/json"),
                   "cache-control": f"public, max-age={BROWSER_SECONDS}, s-maxage={CACHE_SECONDS}"}
        try:
            await cache.put(url, 200, headers, body)
        except Exception as e:  # noqa: BLE001 - a failed store only means the next visitor misses too
            print(f"edge cache put failed: {e}")
        return Response(content=body, status_code=200, headers={**headers, "x-aventra-cache": "miss"})
