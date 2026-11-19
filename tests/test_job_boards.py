"""Job boards (decision 2026-11-19, option C): the Himalayas reader, on a search response saved
live on 2026-11-18 (three of its jobs, descriptions shortened), and the pipeline rules that keep
board jobs only for companies we don't read directly."""

import json
from pathlib import Path

import fetch_jobs as fj
from sources import ADAPTERS, himalayas
from sources.models import Company, Job

FIX = Path(__file__).parent / "fixtures" / "sources"
BOARD = Company("Himalayas", "himalayas", "remote")


def page():
    return json.loads((FIX / "himalayas_search.json").read_text())


class FakeHttp:
    """Serves search pages by page number and records the URLs and headers it was asked with."""

    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def get_json(self, url, fresh_days=None, headers=None):
        self.asked.append((url, headers))
        number = int(url.rsplit("page=", 1)[1])
        return self.pages[number - 1] if number <= len(self.pages) else {"jobs": []}


def test_registered_as_a_daily_board():
    assert ADAPTERS["himalayas"] is himalayas
    assert himalayas.BOARD and himalayas.DAILY


def test_himalayas_job_fields():
    ravelin, tether, micro1 = himalayas.parse(page(), BOARD)
    assert ravelin.id == "himalayas:remote:ravelin/jobs/junior-data-scientist"
    assert ravelin.company == "Ravelin" and ravelin.title == "Junior Data Scientist"
    # The terms: Apply opens applicationLink exactly as given, tracking parameter included.
    assert ravelin.url == "https://himalayas.app/companies/ravelin/jobs/junior-data-scientist?utm_source=api"
    assert ravelin.location_raw == "Remote, United Kingdom" and ravelin.ats_countries == ["United Kingdom"]
    assert ravelin.ats_workplace_type == "remote" and ravelin.employment_type == "Full Time"
    assert ravelin.posted_at == "2026-11-14T03:52:06Z"  # pubDate is in seconds, not milliseconds
    # A long country list is counted in the text and kept whole in the structured field.
    assert tether.location_raw == "Remote, 60 countries" and "India" in tether.ats_countries
    assert micro1.location_raw == "Remote, Worldwide" and micro1.ats_countries == []
    assert "Machine Learning" in micro1.description_text


def test_a_job_found_by_two_queries_is_kept_once():
    assert len(himalayas.parse([page(), page()], BOARD)) == 3


def test_jobs_without_a_link_or_company_are_skipped():
    broken = {"jobs": [{"guid": "https://himalayas.app/companies/x/jobs/y", "title": "ML Engineer",
                        "companyName": "X"}]}  # no applicationLink
    assert himalayas.parse(broken, BOARD) == []


def test_fetch_pages_until_a_short_page_and_sends_the_key(monkeypatch):
    monkeypatch.setattr(himalayas, "settings", lambda: {"queries": ["machine learning", "LLM"],
                                                        "seniority": ["Entry-level", "Mid-level"], "max_pages": 5})
    monkeypatch.setenv("HIMALAYAS_API_KEY", "test-key")
    full = {"jobs": page()["jobs"] * 7}  # 21 jobs: a full page, so the next one is asked for
    http = FakeHttp([full, page()])
    jobs = himalayas.fetch(http, BOARD)
    urls = [u for u, _ in http.asked]
    assert urls[0] == ("https://himalayas.app/jobs/api/search?q=machine+learning"
                       "&seniority=Entry-level%2CMid-level&sort=recent&page=1")
    assert len(urls) == 4  # two pages per query: the second holds 3 jobs, so it is the last
    assert all(h == {"Authorization": "Bearer test-key"} for _, h in http.asked)
    assert len(jobs) == 3


def test_no_key_sends_no_auth_header(monkeypatch):
    monkeypatch.delenv("HIMALAYAS_API_KEY", raising=False)
    assert himalayas.auth_headers() is None


def test_boards_run_only_in_the_daily_run():
    boards = [Company("Glean", "greenhouse", "gleanwork"), BOARD]
    assert [c.name for c in fj.pick(boards, skip_global=True)] == ["Glean"]
    assert [c.name for c in fj.pick(boards)] == ["Glean", "Himalayas"]


def test_company_key_ignores_case_punctuation_and_legal_form():
    assert fj.company_key("Acme AI, Inc.") == fj.company_key("acme ai") == "acmeai"
    assert fj.company_key("Tether Operations Limited") == "tetheroperations"


def _job(source, company, ext="1"):
    return Job(source, ext, company, "remote", "ML Engineer", f"https://x/{ext}", "Remote", "text")


def test_board_jobs_of_companies_we_read_directly_are_dropped():
    direct = [Company("Ravelin", "greenhouse", "ravelin"), BOARD]
    own = _job("greenhouse", "Ravelin", "a")
    board_copy = _job("himalayas", "Ravelin Ltd", "b")
    other = _job("himalayas", "micro1", "c")
    kept, dropped = fj.drop_covered([own, board_copy, other], direct)
    assert kept == [own, other] and dropped == 1


def test_board_leads_are_target_jobs_from_unlisted_companies(tmp_path):
    cfg = tmp_path / "companies.yaml"
    cfg.write_text("companies:\n  - {name: Ravelin, category: applied}\n")
    records = [
        {"source": "himalayas", "company": "micro1", "role_match": True},
        {"source": "himalayas", "company": "micro1", "role_match": True},
        {"source": "himalayas", "company": "Ravelin", "role_match": True},  # already listed
        {"source": "himalayas", "company": "Sales Co", "role_match": False},  # not a target role
        {"source": "greenhouse", "company": "Unlisted", "role_match": True},  # not from a board
    ]
    assert fj.board_leads(records, cfg) == [{"source": "himalayas", "company": "micro1", "target_jobs": 2}]


def test_verifier_reads_one_page(monkeypatch):
    monkeypatch.setattr(himalayas, "settings", lambda: {"queries": ["machine learning"], "seniority": ["Entry-level"]})
    http = FakeHttp([page()])
    assert himalayas.list_titles(http, "remote")[0] == "Junior Data Scientist"
    assert len(http.asked) == 1
