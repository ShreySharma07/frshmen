"""Jobicy (decision 2026-11-19): the reader, on an API response saved live on 2026-11-18 (five of
its data-science jobs, descriptions shortened), its status check, and the pipeline step that
keeps a job open while Jobicy says it is active although its 7-day feed no longer lists it."""

import json
from pathlib import Path

import fetch_jobs as fj
from sources import ADAPTERS, jobicy
from sources.http import FetchError
from sources.models import Company

FIX = Path(__file__).parent / "fixtures" / "sources"
BOARD = Company("Jobicy", "jobicy", "remote")
SKIP = {"Senior", "Lead", "Director", "Manager", "Executive"}


def page():
    return json.loads((FIX / "jobicy_data_science.json").read_text())


class FakeHttp:
    """Serves bodies by URL; records what was asked."""

    def __init__(self, by_url):
        self.by_url, self.asked = by_url, []

    def get_json(self, url, fresh_days=None, headers=None):
        self.asked.append(url)
        return self.by_url.get(url)


def test_registered_as_a_daily_board():
    assert ADAPTERS["jobicy"] is jobicy and jobicy.BOARD and jobicy.DAILY


def test_job_fields():
    jobs = {j.company: j for j in jobicy.parse(page(), BOARD, SKIP)}
    hume = jobs["Hume AI"]
    assert hume.id == "jobicy:remote:163134"
    assert hume.title == "AI Researcher" and hume.url == "https://jobicy.com/jobs/163134-ai-researcher-3"
    assert hume.location_raw == "Remote, USA" and hume.ats_workplace_type == "remote"
    assert hume.posted_at == "2026-11-18T13:57:24Z"
    assert hume.employment_type == "Full-Time" and hume.department == "Data Science & Analytics"
    assert jobs["Supabase"].location_raw == "Remote, Anywhere"
    assert jobs["Invisible Technologies"].location_raw == "Remote, LATAM"


def test_senior_and_up_levels_are_skipped():
    assert "Monzo" not in {j.company for j in jobicy.parse(page(), BOARD, SKIP)}  # jobLevel "Senior"
    assert "Monzo" in {j.company for j in jobicy.parse(page(), BOARD)}


def test_a_job_in_two_categories_is_kept_once():
    assert len(jobicy.parse([page(), page()], BOARD, SKIP)) == 4


def test_fetch_follows_the_cursor_per_category(monkeypatch):
    monkeypatch.setattr(jobicy, "settings", lambda: {"industries": ["data-science"], "max_pages": 5,
                                                     "skip_levels": sorted(SKIP)})
    first = dict(page(), nextCursor="abc==")
    http = FakeHttp({jobicy.jobs_url("data-science"): first,
                     jobicy.jobs_url("data-science", "abc=="): dict(page(), nextCursor=None)})
    assert len(jobicy.fetch(http, BOARD)) == 4
    assert http.asked == ["https://jobicy.com/api/jobs?count=100&industry=data-science",
                          "https://jobicy.com/api/jobs?count=100&industry=data-science&cursor=abc%3D%3D"]


def test_still_open_keeps_only_active_and_batches_by_100():
    ids = [str(i) for i in range(1, 151)]
    first = f"{jobicy.STATUS_URL}?ids=" + "%2C".join(ids[:100])
    second = f"{jobicy.STATUS_URL}?ids=" + "%2C".join(ids[100:])
    http = FakeHttp({first: {"jobs": [{"id": 1, "status": "active"}, {"id": 2, "status": "closed"}]},
                     second: {"jobs": [{"id": 101, "status": "unknown"}, {"id": 150, "status": "active"}]}})
    assert jobicy.still_open(http, ids + ["not-a-number"]) == {"1", "150"}
    assert len(http.asked) == 2


class Adapter:
    """A board adapter with a status check, for keep_still_open."""
    NAME, BOARD = "windowed", True

    def __init__(self, active=(), fail=False):
        self.active, self.fail, self.asked = set(active), fail, []

    def still_open(self, http, ids):
        self.asked.append(ids)
        if self.fail:
            raise FetchError("status: HTTP 503")
        return self.active & set(ids)


def test_keep_still_open_asks_only_about_missing_uncovered_jobs(monkeypatch):
    adapter = Adapter(active={"2", "3"})
    monkeypatch.setitem(fj.ADAPTERS, "windowed", adapter)
    board = Company("Windowed", "windowed", "remote")
    stored = {"windowed:remote:1": "Acme", "windowed:remote:2": "Beta", "windowed:remote:3": "Ravelin Ltd"}
    keep, unchecked = fj.keep_still_open(None, [board], fetched={"windowed:remote:1"}, covered={"ravelin"},
                                         dsn="postgresql://x", stored=lambda dsn, prefix: list(stored.items()))
    assert adapter.asked == [["2"]]  # 1 is in today's feed; 3's company is read directly
    assert keep == ["windowed:remote:2"] and unchecked == set()


def test_board_without_a_check_closes_nothing(monkeypatch):
    monkeypatch.setitem(fj.ADAPTERS, "windowed", Adapter(fail=True))
    board = Company("Windowed", "windowed", "remote")
    assert fj.keep_still_open(None, [board], set(), set(), dsn=None) == ([], {"Windowed"})
    stored = lambda dsn, prefix: [("windowed:remote:9", "Beta")]  # noqa: E731
    assert fj.keep_still_open(None, [board], set(), set(), "postgresql://x", stored) == ([], {"Windowed"})


def test_boards_without_a_status_check_are_left_alone():
    assert fj.keep_still_open(None, [Company("Glean", "greenhouse", "gleanwork")], set(), set(), dsn=None) == ([], set())
