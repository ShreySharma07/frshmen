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
    assert "aventra-jobboard" in seen[0].get_header("User-agent")


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


def test_malformed_address_is_a_fetch_error_not_a_crash(monkeypatch, no_sleep):
    # One bad `website` in companies.yaml must cost one company, not the whole run.
    import http.client
    _serve(monkeypatch, [http.client.InvalidURL("URL can't contain control characters. 'acme.io, https'")])
    with pytest.raises(FetchError, match="acme.io, https"):
        HttpClient().get_text("https://acme.io, https:/robots.txt")
    assert no_sleep == []  # not retried: asking again can't fix the address


def test_dropped_connection_is_retried_then_a_fetch_error(monkeypatch, no_sleep):
    # 2026-11-12: a site closed the connection mid-response during careers detection; the
    # http.client error escaped and stopped the run at company 179 of 461.
    import http.client
    _serve(monkeypatch, [http.client.RemoteDisconnected("Remote end closed connection without response"),
                         _Resp(b"<html>ok</html>")])
    assert HttpClient().get_text("https://www.firstcry.com/careers") == "<html>ok</html>"
    _serve(monkeypatch, [ConnectionResetError("reset")] * 5)
    with pytest.raises(FetchError, match="www.firstcry.com"):
        HttpClient().get_text("https://www.firstcry.com/careers")


# --- non-ASCII URLs from sitemaps (Philips, BCG) -------------------------------------


def test_cjk_path_is_percent_encoded_before_sending(monkeypatch, no_sleep):
    seen = []
    _serve(monkeypatch, [_Resp(b"<html></html>")], seen)
    HttpClient().get_text("https://www.careers.philips.com/global/en/job/592260/抖音营销经理")
    assert seen[0].full_url == ("https://www.careers.philips.com/global/en/job/592260/"
                                "%E6%8A%96%E9%9F%B3%E8%90%A5%E9%94%80%E7%BB%8F%E7%90%86")
    seen[0].selector.encode("ascii")  # what http.client does with the request line


def test_zero_width_space_is_encoded_not_stripped(monkeypatch, no_sleep):
    # BCG serves the page at the %E2%80%8B form; the stripped URL only redirects back to it.
    seen = []
    _serve(monkeypatch, [_Resp(b"<html></html>")], seen)
    HttpClient().get_text("https://careers.bcg.com/global/en/job/59322/"
                          "Delivery-AI-Software-Engineer​ing-Senior-Manager")
    assert seen[0].full_url == ("https://careers.bcg.com/global/en/job/59322/"
                                "Delivery-AI-Software-Engineer%E2%80%8Bing-Senior-Manager")


def test_already_encoded_url_is_not_encoded_twice():
    url = "https://careers.bcg.com/job/59322/Engineer%E2%80%8Bing?q=ml%20engineer&loc=Pune"
    assert http_mod.ascii_url(url) == url
    # Mixed: a raw character next to an encoded one; only the raw one changes.
    assert http_mod.ascii_url("https://x.com/a%20b/é?q=c%2Fd&r=ü") == "https://x.com/a%20b/%C3%A9?q=c%2Fd&r=%C3%BC"


def test_non_ascii_host_is_idna_encoded():
    assert http_mod.ascii_url("https://bücher.example:8443/jobs/1") == "https://xn--bcher-kva.example:8443/jobs/1"


def test_ascii_url_keeps_its_cache_key(tmp_path, monkeypatch, no_sleep):
    url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"
    assert http_mod.ascii_url(url) is url
    _serve(monkeypatch, [_Resp(b'{"jobs": []}', {"ETag": '"v1"'})])
    client = HttpClient(cache_dir=tmp_path)
    client.get_json(url)
    assert client._cache_path(url).exists()


def test_raw_and_encoded_forms_share_one_cache_entry(tmp_path, monkeypatch, no_sleep):
    seen = []
    _serve(monkeypatch, [_Resp(b"page", {"ETag": '"v1"'}), _http_error(304)], seen)
    client = HttpClient(cache_dir=tmp_path)
    client.get_text("https://x.com/job/é")
    assert client.get_text("https://x.com/job/%C3%A9") == "page"
    assert seen[1].get_header("If-none-match") == '"v1"'
