"""HN "Who is hiring?" adapter, on a thread in the Algolia items API shape (search hit shape seen live 2026-10-07)."""

from extract.classify import classify
from extract.location import extract_location
from sources import hn
from sources.models import Company

HN = Company("HN Who is hiring", "hn", "whoishiring")

THREAD = {
    "id": 49922569, "title": "Ask HN: Who is hiring? (October 2026)", "author": "whoishiring",
    "children": [
        {"id": 1, "created_at": "2026-10-01T16:00:00.000Z", "author": "a",
         "text": "Acme AI (https://acme.ai) | ML Engineer, New Grad | Bangalore, India | ONSITE<p>"
                 "We train speech models. 2026 graduates welcome; Python and PyTorch.<p>Apply: jobs@acme.ai",
         "children": [{"id": 11, "text": "Is this remote?", "children": []}]},
        {"id": 2, "created_at": "2026-10-02T09:30:00.000Z", "author": "b",
         "text": "Globex | Senior Backend Engineer | REMOTE (US) | https:&#x2F;&#x2F;globex.com&#x2F;careers<p>"
                 "5+ years of Python experience required.", "children": []},
        {"id": 3, "created_at": "2026-10-02T10:00:00.000Z", "author": "c",
         "text": "Just a comment without the header convention.", "children": []},
        {"id": 4, "created_at": "2026-10-03T10:00:00.000Z", "author": None, "text": None, "children": []},
    ],
}


class FakeHttp:
    def __init__(self, routes):
        self.routes = routes

    def get_json(self, url, fresh_days=None):
        return self.routes.get(url)


def test_parse_reads_header_convention_and_skips_the_rest():
    jobs = hn.parse(THREAD, HN)
    assert [j.external_id for j in jobs] == ["1", "2"]  # header-less comment and deleted post skipped
    acme, globex = jobs
    assert (acme.company, acme.title) == ("Acme AI", "ML Engineer, New Grad")
    assert acme.url == "https://news.ycombinator.com/item?id=1"
    assert acme.posted_at == "2026-10-01T16:00:00Z"
    assert "2026 graduates welcome" in acme.description_text
    assert extract_location(acme.location_raw).cities == ["Bengaluru"]
    assert (globex.company, globex.title) == ("Globex", "Senior Backend Engineer")
    assert extract_location(globex.location_raw).countries == ["United States"]


def test_posts_go_through_the_same_classifier():
    acme, globex = hn.parse(THREAD, HN)
    assert classify(acme.title, acme.description_text).level == "fresher"
    assert classify(globex.title, globex.description_text).level == "experienced"


def test_fetch_finds_the_latest_hiring_thread_not_the_wants_to_be_hired_one():
    search = {"hits": [{"objectID": "49922568", "title": "Ask HN: Who wants to be hired? (October 2026)"},
                       {"objectID": "49922569", "title": "Ask HN: Who is hiring? (October 2026)"}]}
    http = FakeHttp({hn.SEARCH_URL: search, hn.item_url("49922569"): THREAD})
    assert len(hn.fetch(http, HN)) == 2
    assert hn.list_titles(http, "whoishiring") == ["ML Engineer, New Grad", "Senior Backend Engineer"]
