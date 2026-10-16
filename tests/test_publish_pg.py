"""Supabase publisher: repost matching and id resolution, then the full publish rules against
Postgres (PG_TEST_URL; CI runs a Postgres service, skipped without it)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

import job_rows
import publish_pg as p

TEXT = " ".join(f"word{i}" for i in range(200))  # a long, distinctive description


def row(id_, text=TEXT, posted="2026-10-01T00:00:00Z", title="SDE Fresher", company="A", loc="Pune"):
    return {"id": id_, "description_text": text, "posted_at": posted,
            "repost_key": p.repost_key(company, title, loc)}


def test_repost_key_ignores_case_spacing_and_punctuation():
    assert p.repost_key("Acme", "SDE - Fresher", "Pune, India") == p.repost_key("acme ", "sde fresher", "pune india")
    assert p.repost_key("Acme", "SDE Fresher", "Pune") != p.repost_key("Acme", "SDE Fresher", "Delhi")


def test_same_posting_needs_near_identical_text():
    assert p.same_posting(TEXT, TEXT + " apply now")
    assert not p.same_posting(TEXT, " ".join(f"other{i}" for i in range(200)))
    assert not p.same_posting("", "")  # no evidence, no merge


def test_new_listing_of_a_stored_job_merges_into_it():
    new = row("ashby:a:2", posted="2026-10-16T00:00:00Z")
    targets, aliases = p.resolve([new], known={"ashby:a:1"}, aliases={},
                                 candidates={new["repost_key"]: [("ashby:a:1", TEXT)]})
    assert aliases == {"ashby:a:2": "ashby:a:1"} and targets == {"ashby:a:1": new}


def test_different_text_under_the_same_title_stays_a_separate_job():
    new = row("ashby:a:2", text=" ".join(f"batch2_{i}" for i in range(200)))
    targets, aliases = p.resolve([new], known={"ashby:a:1"}, aliases={},
                                 candidates={new["repost_key"]: [("ashby:a:1", TEXT)]})
    assert aliases == {} and set(targets) == {"ashby:a:2"}


def test_known_alias_and_both_listings_live_keep_one_job_with_the_newer_date():
    old, new = row("ashby:a:1", posted="2026-09-16T00:00:00Z"), row("ashby:a:2", posted="2026-10-16T00:00:00Z")
    targets, aliases = p.resolve([old, new], known={"ashby:a:1"}, aliases={"ashby:a:2": "ashby:a:1"}, candidates={})
    assert aliases == {} and targets == {"ashby:a:1": new}


def test_board_prefixes_match_only_that_boards_ids():
    prefixes = p.board_prefixes([{"source": "lever", "company_slug": "acme"}])
    assert "lever:acme:123".startswith(prefixes) and not "lever:acme2:1".startswith(prefixes)


# --- Against Postgres (PG_TEST_URL; CI runs a Postgres service) ------------------------------

PG = os.environ.get("PG_TEST_URL")
needs_pg = pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")
T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
LONG = " ".join(f"w{i}" for i in range(200))


def job(ext="1", slug="acme", title="ML Engineer", desc=LONG, level="fresher", content=None, posted=None):
    return {
        "id": f"ashby:{slug}:{ext}", "source": "ashby", "company": slug.title(), "company_slug": slug,
        "title": title, "url": f"https://x/{ext}", "location_raw": "Remote", "ats_workplace_type": "remote",
        "ats_countries": ["IN"], "department": None, "employment_type": None, "posted_at": posted,
        "description_text": desc, "content_hash": content or f"h-{ext}-{hash(desc)}", "level": level,
        "level_confidence": 0.9, "reason": "fresher signal", "yoe_min": None, "yoe_max": None,
        "yoe_evidence": None, "batch_years": [2026], "evidence": [{"kind": "fresher_text", "snippet": "new grads"}],
        "role_match": True, "role_family": "ai_ml", "role_reason": "title matches 'ml engineer'",
        "role_evidence": [{"kind": "title", "snippet": title}],
    }


@pytest.fixture
def pg():
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA public; "
                     "CREATE SCHEMA auth; CREATE TABLE auth.users (id uuid PRIMARY KEY); "
                     "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS 'SELECT NULL::uuid'")
        for f in sorted(Path("db/postgres").glob("*.sql")):
            conn.execute(f.read_text())
        yield conn


def run(pg, jobs, hours, boards=(("ashby", "acme"),)):
    payload = {"jobs": jobs, "boards_ok": [{"source": s, "company_slug": c} for s, c in boards], "errors": {}}
    return p.publish(pg, payload, now=T0 + timedelta(hours=hours))


def one(pg, sql, *args):
    return pg.execute(sql, args or None).fetchone()


@needs_pg
def test_first_publish_then_unchanged_run_writes_nothing(pg):
    assert run(pg, [job("1"), job("2")], 0)["new"] == 2
    assert one(pg, "SELECT first_seen_at, status, role_reason FROM job_cards WHERE id = 'ashby:acme:1'") == (
        T0, "open", "title matches 'ml engineer'")
    assert set(run(pg, [job("1"), job("2")], 3).values()) == {0}
    assert one(pg, "SELECT value->>'total' FROM meta WHERE key = 'filters'") == ("2",)


@needs_pg
def test_changed_content_updates_but_keeps_first_seen(pg):
    run(pg, [job("1", desc="Python")], 0)
    assert run(pg, [job("1", desc="Needs 3+ years", level="experienced")], 3)["changed"] == 1
    assert one(pg, "SELECT level, description_text, first_seen_at FROM job_cards WHERE id = 'ashby:acme:1'") == (
        "experienced", "Needs 3+ years", T0)


@needs_pg
def test_missing_job_closes_after_two_misses_and_reopens_when_back(pg):
    run(pg, [job("1"), job("2")], 0)
    assert run(pg, [job("1")], 3)["missed"] == 1
    assert run(pg, [job("1")], 6)["closed"] == 1
    assert one(pg, "SELECT status FROM jobs WHERE id = 'ashby:acme:2'") == ("closed",)
    assert run(pg, [job("1"), job("2")], 9)["reopened"] == 1
    assert one(pg, "SELECT status, missed_runs FROM jobs WHERE id = 'ashby:acme:2'") == ("open", 0)


@needs_pg
def test_failed_board_does_not_close_its_jobs(pg):
    run(pg, [job("1")], 0)
    for h in (3, 6, 9):
        run(pg, [], h, boards=())
    assert one(pg, "SELECT status, missed_runs FROM jobs WHERE id = 'ashby:acme:1'") == ("open", 0)


@needs_pg
def test_rules_bump_keeps_current_and_previous_label(pg, monkeypatch):
    run(pg, [job("1")], 0)
    run(pg, [job("1", level="maybe")], 3)  # same rules version: label updated in place
    monkeypatch.setattr(job_rows, "EXTRACT_VERSION", job_rows.EXTRACT_VERSION + 1)
    assert run(pg, [job("1", level="experienced")], 6)["reclassified"] == 1
    rows = pg.execute("SELECT level, is_current FROM job_labels WHERE job_id = 'ashby:acme:1' "
                      "ORDER BY rules_version").fetchall()
    assert rows == [("maybe", False), ("experienced", True)]
    assert one(pg, "SELECT level FROM job_cards WHERE id = 'ashby:acme:1'") == ("experienced",)


@needs_pg
def test_repost_merges_into_the_original_with_the_new_date_and_link(pg):
    run(pg, [job("1", content="c")], 0)
    rep = job("9", content="c", posted="2026-10-20T00:00:00Z")
    assert run(pg, [rep], 3)["reposts"] == 1
    assert one(pg, "SELECT count(*) FROM jobs") == (1,)
    assert one(pg, "SELECT url, posted_at, first_seen_at FROM jobs WHERE id = 'ashby:acme:1'") == (
        "https://x/9", datetime(2026, 10, 20, tzinfo=timezone.utc), T0)
    assert one(pg, "SELECT job_id FROM job_aliases WHERE alias_id = 'ashby:acme:9'") == ("ashby:acme:1",)
    assert set(run(pg, [rep], 6).values()) == {0}  # the alias now routes the listing straight there


@needs_pg
def test_quotes_and_huge_text_survive(pg):
    run(pg, [job("1", title="O'Reilly's ML Engineer", desc="x" * 100_000)], 0)
    title, size = one(pg, "SELECT title, length(description_text) FROM jobs")
    assert title == "O'Reilly's ML Engineer" and size == job_rows.MAX_DESCRIPTION_CHARS
