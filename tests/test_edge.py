"""Rate limits and the public-data cache in front of the API (api/src/edge.py; docs/decisions.md,
2026-11-18, security review M2). Fakes stand in for Cloudflare's binding and cache.
Needs PG_TEST_URL, like tests/test_api.py."""

from datetime import datetime, timezone

import pytest

from test_api import PG, TOKEN, app_client, publish, records, reset

pytestmark = pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")


class Budget:
    """A limiter that allows `n` calls per key, like the binding within one window."""

    def __init__(self, n):
        self.n, self.seen = n, {}

    async def allow(self, key):
        self.seen[key] = self.seen.get(key, 0) + 1
        return self.seen[key] <= self.n


class Memory:
    def __init__(self):
        self.store, self.puts = {}, 0

    async def get(self, url):
        return self.store.get(url)

    async def put(self, url, status, headers, body):
        self.puts += 1
        self.store[url] = (status, headers, body)


@pytest.fixture
def client():
    reset()
    publish(records(), datetime.now(timezone.utc))
    return app_client()


def test_too_many_requests_from_one_visitor_get_429(client):
    client.app.state.limiters = (Budget(3), None)
    codes = [client.get("/api/meta", headers={"CF-Connecting-IP": "203.0.113.7"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    # Another visitor has their own budget.
    assert client.get("/api/meta", headers={"CF-Connecting-IP": "198.51.100.2"}).status_code == 200


def test_the_ai_budget_applies_only_to_gemini_routes(client):
    ai = Budget(0)
    client.app.state.limiters = (Budget(100), ai)
    assert client.get("/api/meta").status_code == 200
    res = client.post("/api/agent/chat", json={"messages": [{"role": "user", "text": "hi"}]})
    assert res.status_code == 429 and res.headers["Retry-After"] == "60"
    assert client.post("/api/jobs/x/fit").status_code == 429
    assert set(ai.seen) == {"ai:testclient"}


def test_public_data_is_served_from_the_cache_the_second_time(client):
    cache = Memory()
    client.app.state.cache = cache
    first = client.get("/api/jobs?yrs=0")
    second = client.get("/api/jobs?yrs=0")
    assert first.headers["x-aventra-cache"] == "miss" and second.headers["x-aventra-cache"] == "hit"
    assert first.json() == second.json() and cache.puts == 1
    assert "s-maxage=300" in first.headers["cache-control"]
    # A different query is a different page.
    assert client.get("/api/jobs?yrs=3").headers["x-aventra-cache"] == "miss"


def test_signed_in_and_private_requests_never_touch_the_cache(client):
    cache = Memory()
    client.app.state.cache = cache
    assert "x-aventra-cache" not in client.get("/api/jobs", headers=TOKEN).headers
    assert "x-aventra-cache" not in client.get("/api/fit/quota").headers  # not a public route
    assert cache.puts == 0


def test_errors_are_not_cached(client):
    cache = Memory()
    client.app.state.cache = cache
    assert client.get("/api/jobs?page=101").status_code == 422
    assert cache.puts == 0


def test_paging_stops_at_two_thousand_jobs(client):
    assert client.get("/api/jobs?page=100").status_code == 200
    res = client.get("/api/jobs?page=101")
    assert res.status_code == 422 and "narrow the filters" in res.json()["detail"]
