"""scripts/refresh_startups.py and extract/startup.py (docs/decisions.md, 2026-11-16)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import refresh_startups as rs  # noqa: E402
from extract.startup import categories_for  # noqa: E402

NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)
YC = [{"name": "Vectorly", "website": "https://vectorly.ai", "one_liner": "LLM evals for AI teams",
       "long_description": "We help teams test LLM apps with Python SDKs.", "tags": ["Generative AI", "Developer Tools"],
       "industries": ["B2B"], "status": "Active"},
      {"name": "Twin", "website": "https://twin-a.com", "one_liner": "A"}, {"name": "Twin", "website": "https://twin-b.com", "one_liner": "B"}]


def company(name, website=None, csv_description=None, notes=None):
    return {"key": name.lower(), "name": name, "website": website, "csv_description": csv_description, "notes": notes}


class Fetch:
    def __init__(self, *answers):
        self.answers, self.urls = list(answers), []

    def __call__(self, url, etag, modified):
        self.urls.append((url, etag, modified))
        return self.answers.pop(0)


def allow(url):
    return True


def test_categories_from_tags_and_words_never_from_a_name():
    assert categories_for(["Generative AI"], None) == ["ai_ml"]
    assert categories_for([], "APIs for payments") == ["backend", "software", "fullstack"]
    assert categories_for([], "Mail for real estate agents") == []  # "agents" alone isn't AI
    assert categories_for([], None) == []


def test_meta_description_prefers_name_then_og():
    assert rs.meta_description('<head><meta property="og:description" content="OG"><meta content="Voice AI &amp; more" name="description"></head>') == "Voice AI & more"
    assert rs.meta_description("<meta property='og:description' content='Robots for farms'>") == "Robots for farms"
    assert rs.meta_description("<title>x</title>") is None


def test_csv_beats_yc_and_yc_matches_by_website_first():
    index = rs.index_yc(YC)
    assert rs.find_yc(index, "Twin", None) is None  # two companies share the name
    assert rs.find_yc(index, "Twin", "twin-b.com")["one_liner"] == "B"
    row, fetched = rs.build(company("Vectorly", csv_description="Evals for agents"), rs.find_yc(index, "Vectorly", None),
                            None, NOW, Fetch(), allow)
    assert (row["one_liner"], row["source"], fetched) == ("Evals for agents", "csv", False)
    assert "ai_ml" in row["categories"] and row["status"] == "Active"  # tags still come from yc-oss
    row, _ = rs.build(company("Vectorly"), rs.find_yc(index, "Vectorly", None), None, NOW, Fetch(), allow)
    assert row["source"] == "yc-oss" and row["website"] == "https://vectorly.ai" and "Python" in row["skills"]


def test_homepage_read_once_a_month_politely():
    fetch = Fetch((200, "Robots that pick strawberries", '"v1"', None))
    row, fetched = rs.build(company("Pickr", "https://pickr.io"), None, None, NOW, fetch, allow)
    assert fetched and row["source"] == "homepage" and row["categories"] == ["hardware"] and row["homepage_etag"] == '"v1"'
    # A week later: not due, nothing fetched, the description stays.
    again, fetched = rs.build(company("Pickr", "https://pickr.io"), None, {**row, "key": "pickr"},
                              NOW + timedelta(days=7), Fetch(), allow)
    assert not fetched and again["one_liner"] == "Robots that pick strawberries"
    # A month later: asked with the ETag; 304 keeps it.
    fetch = Fetch((304, None, None, None))
    again, fetched = rs.build(company("Pickr", "https://pickr.io"), None, {**row, "key": "pickr"},
                              NOW + timedelta(days=31), fetch, allow)
    assert fetch.urls == [("https://pickr.io", '"v1"', None)] and again["source"] == "homepage"


def test_robots_and_missing_descriptions_leave_it_unknown():
    row, fetched = rs.build(company("Shy", "https://shy.dev"), None, None, NOW, Fetch(), lambda url: False)
    assert not fetched and row["one_liner"] is None and row["categories"] == []
    row, fetched = rs.build(company("Blank", "blank.dev"), None, None, NOW, Fetch((200, None, None, None)), allow)
    assert fetched and row["source"] is None and row["website"] == "https://blank.dev"


def test_status_from_csv_notes():
    row, _ = rs.build(company("Old", notes="Company status: Inactive"), None, None, NOW, None, allow)
    assert row["status"] == "Inactive"


PG = __import__("os").environ.get("PG_TEST_URL")


@pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")
def test_refresh_writes_only_changes_and_drops_removed_startups():
    from test_api import reset

    reset()
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("INSERT INTO contacts (kind, name, company, company_url, source) VALUES "
                     "('founder', 'Mo', 'Vectorly', NULL, 't'), ('founder', 'Al', 'Pickr', 'https://pickr.io', 't'), "
                     "('hr', 'Ravi', 'Razorpay', NULL, 't')")
        first = rs.refresh(conn, YC, Fetch((200, "Robots for farms", None, None)), allow, NOW)
        assert first == {"companies": 2, "written": 2, "homepages": 1, "described": 2, "removed": 0}
        assert rs.refresh(conn, YC, Fetch(), allow, NOW)["written"] == 0
        conn.execute("DELETE FROM contacts WHERE company = 'Pickr'")
        assert rs.refresh(conn, YC, Fetch(), allow, NOW)["removed"] == 1
        assert [r[0] for r in conn.execute("SELECT key FROM startup_profiles")] == ["vectorly"]
