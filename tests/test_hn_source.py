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


# Seen live 2026-11-12 (reported by Shrey): people post their own profile in the hiring thread,
# often in the same "Name | Role | Place" shape as a company's post, and it was listed as a job.
PROFILE = ("Hemant Singh | Software Engineer / Backend Engineer | India (REMOTE / ONSITE)<p>"
           "I'm a software engineer focused on backend development, primarily working with Java, Spring Boot, "
           "and Python. I enjoy building backend systems, REST APIs, and distributed applications, with an "
           "interest in system design and Agentic AI.")
TEMPLATE = ("Location: Pune, India<p>Remote: Yes<p>Willing to relocate: Yes<p>Technologies: Python, Go | Kubernetes<p>"
            "Résumé/CV: https://example.com/cv.pdf<p>Email: someone@example.com")
SEEKING = "Jane Doe | ML Engineer | Berlin<p>Seeking a new role in applied ML after 4 years at a startup. My portfolio: example.com"
FOUNDER = ("Initech | Founding ML Engineer | Bengaluru | ONSITE<p>I'm a second-time founder and we're hiring our first "
           "ML engineer. I am an engineer myself, so you'd work with me directly. Apply: jobs@initech.example")
SOLO = "Hooli | Backend Engineer | REMOTE<p>I'm the CTO. Looking for a backend engineer with 2+ years of Go. Email me."


LOOKING = "Sam Lee | Data Scientist | Remote (EU)<p>I'm looking for a new full-time role. 3 years of Python and SQL."


def thread(*texts):
    return {"children": [{"id": i, "created_at": "2026-11-01T10:00:00.000Z", "text": t, "children": []} for i, t in enumerate(texts, 1)]}


def test_a_persons_own_profile_in_the_hiring_thread_is_not_a_job():
    assert hn.parse(thread(PROFILE, TEMPLATE, SEEKING, LOOKING), HN) == []


def test_a_hiring_post_written_in_the_first_person_is_still_a_job():
    jobs = hn.parse(thread(FOUNDER, SOLO, PROFILE), HN)
    assert [(j.company, j.title) for j in jobs] == [("Initech", "Founding ML Engineer"), ("Hooli", "Backend Engineer")]
