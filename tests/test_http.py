import io
import json
import urllib.error

import pytest

from sources import http as http_mod
from sources.http import FetchError, HttpClient


class _Resp:
    def __init__(self, body: bytes, headers: dict | None = None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *a):
        return self.body


def _http_error(code, headers=None):
    return urllib.error.HTTPError("u", code, "err", headers or {}, io.BytesIO())


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(http_mod.time, "sleep", sleeps.append)
    return sleeps


def _serve(monkeypatch, responses, seen_requests=None):
    def urlopen(req, timeout):
        if seen_requests is not None:
            seen_requests.append(req)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(http_mod.urllib.request, "urlopen", urlopen)


def test_backs_off_on_429_then_succeeds(monkeypatch, no_sleep):
    _serve(monkeypatch, [_http_error(429, {"Retry-After": "7"}), _Resp(b'{"jobs": []}')])
    assert HttpClient().get_json("https://api.ashbyhq.com/x") == {"jobs": []}
    assert 7.0 in no_sleep


def test_retry_after_zero_still_backs_off(no_sleep):
    HttpClient()._back_off("h", 0, "0")
    assert no_sleep == [5.0]


def test_gives_up_with_fetch_error(monkeypatch, no_sleep):
    _serve(monkeypatch, [_http_error(429)] * 5)
    with pytest.raises(FetchError, match="api.lever.co: HTTP 429"):
        HttpClient().get_json("https://api.lever.co/x")


def test_404_means_not_found(monkeypatch, no_sleep):
    _serve(monkeypatch, [_http_error(404)])
    assert HttpClient().get_json("https://api.lever.co/x") is None


def test_sends_identifying_user_agent(monkeypatch, no_sleep):
    seen = []
    _serve(monkeypatch, [_Resp(b"[]")], seen)
    HttpClient().get_json("https://api.lever.co/x")
    assert "frshmen-jobboard" in seen[0].get_header("User-agent")


def test_etag_revalidation_serves_cached_body_on_304(monkeypatch, no_sleep, tmp_path):
    seen = []
    body = {"jobs": [{"id": 1}]}
    _serve(monkeypatch, [_Resp(json.dumps(body).encode(), {"ETag": '"v1"'}), _http_error(304)], seen)
    client = HttpClient(cache_dir=tmp_path)
    assert client.get_json("https://boards-api.greenhouse.io/x") == body
    assert client.get_json("https://boards-api.greenhouse.io/x") == body
    assert seen[1].get_header("If-none-match") == '"v1"'


def test_no_cache_entry_without_validators(monkeypatch, no_sleep, tmp_path):
    _serve(monkeypatch, [_Resp(b"[]")])
    HttpClient(cache_dir=tmp_path).get_json("https://api.lever.co/x")
    assert list(tmp_path.iterdir()) == []


def test_pacing_reserves_slots_per_host_across_threads(monkeypatch):
    # Two requests to one host from different threads must still be spaced; other hosts don't wait.
    clock = [100.0]
    sleeps = []
    monkeypatch.setattr(http_mod.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(http_mod.time, "sleep", sleeps.append)
    client = HttpClient()
    client._pace("a.example")
    client._pace("a.example")  # same instant, as if from a second thread
    client._pace("b.example")
    assert sleeps == [http_mod.MIN_SECONDS_PER_HOST]
