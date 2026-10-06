import json

import pytest

import publish_d1 as pub


def job(ext="1", slug="acme", title="ML Engineer", desc="Python", level="fresher", content=None, source="ashby"):
    return {
        "id": f"{source}:{slug}:{ext}", "source": source, "company": slug.title(), "company_slug": slug,
        "title": title, "url": f"https://x/{ext}", "location_raw": "Remote", "ats_workplace_type": "remote",
        "ats_countries": ["IN"], "department": None, "employment_type": None, "posted_at": None,
        "description_text": desc, "content_hash": content or f"h-{ext}-{desc}", "level": level,
        "level_confidence": 0.9, "reason": "fresher signal", "yoe_min": None, "yoe_max": None,
        "yoe_evidence": None, "batch_years": [2026], "evidence": [{"kind": "fresher_text", "snippet": "new grads"}],
        "role_match": True, "role_family": "ai_ml", "role_reason": "title matches 'ml engineer'",
        "role_evidence": [{"kind": "title", "snippet": title}],
    }


def payload(jobs, boards=(("ashby", "acme"),), errors=None):
    return {"jobs": jobs, "boards_ok": [{"source": s, "company_slug": c} for s, c in boards], "errors": errors or {}}


@pytest.fixture
def db(tmp_path):
    return pub.SqliteDatabase(tmp_path / "t.db")


def rows(db):
    return {r["id"]: r for r in db.query("SELECT * FROM jobs")}


def test_first_publish_inserts_with_first_seen(db):
    p = pub.publish(db, payload([job("1"), job("2")]), now="2026-10-06T00:00:00Z")
    assert (p.new, p.changed, p.closed) == (2, 0, 0)
    r = rows(db)["ashby:acme:1"]
    assert r["first_seen_at"] == "2026-10-06T00:00:00Z" and r["status"] == "open" and r["role_match"] == 1
    assert json.loads(r["batch_years"]) == [2026]
    assert json.loads(r["evidence"])["level"][0]["snippet"] == "new grads"


def test_unchanged_jobs_are_not_written(db):
    pub.publish(db, payload([job("1")]), now="2026-10-06T00:00:00Z")
    p = pub.publish(db, payload([job("1")]), now="2026-10-07T00:00:00Z")
    assert p.sql == ""  # nothing but the run row: the write budget stays untouched


def test_changed_content_updates_but_keeps_first_seen(db):
    pub.publish(db, payload([job("1", desc="Python")]), now="2026-10-06T00:00:00Z")
    p = pub.publish(db, payload([job("1", desc="Needs 3+ years", level="experienced")]), now="2026-10-07T00:00:00Z")
    r = rows(db)["ashby:acme:1"]
    assert p.changed == 1
    assert (r["level"], r["description_text"], r["first_seen_at"]) == ("experienced", "Needs 3+ years", "2026-10-06T00:00:00Z")


def test_missing_job_is_closed_after_two_misses_not_deleted(db):
    pub.publish(db, payload([job("1"), job("2")]), now="t1")
    p = pub.publish(db, payload([job("1")]), now="t2")
    assert (p.missed, p.closed) == (1, 0) and rows(db)["ashby:acme:2"]["status"] == "open"
    p = pub.publish(db, payload([job("1")]), now="t3")
    assert p.closed == 1 and rows(db)["ashby:acme:2"]["status"] == "closed"


def test_one_miss_then_seen_again_resets_the_count(db):
    pub.publish(db, payload([job("1"), job("2")]), now="t1")
    pub.publish(db, payload([job("1")]), now="t2")
    p = pub.publish(db, payload([job("1"), job("2")]), now="t3")
    assert p.reopened == 0 and rows(db)["ashby:acme:2"]["missed_runs"] == 0
    p = pub.publish(db, payload([job("1")]), now="t4")
    assert p.closed == 0 and rows(db)["ashby:acme:2"]["status"] == "open"


def test_migrations_run_once(tmp_path):
    path = tmp_path / "m.db"
    pub.SqliteDatabase(path).migrate()
    pub.SqliteDatabase(path).migrate()  # a second ALTER TABLE would raise "duplicate column"


def test_failed_board_does_not_close_its_jobs(db):
    pub.publish(db, payload([job("1", slug="acme"), job("9", slug="other")], boards=[("ashby", "acme"), ("ashby", "other")]), now="t1")
    p = pub.publish(db, payload([job("1", slug="acme")], boards=[("ashby", "acme")], errors={"Other": "HTTP 429"}), now="t2")
    assert p.closed == 0 and rows(db)["ashby:other:9"]["status"] == "open"


def test_reappearing_job_is_reopened(db):
    pub.publish(db, payload([job("1"), job("2")]), now="t1")
    pub.publish(db, payload([job("1")]), now="t2")
    pub.publish(db, payload([job("1")]), now="t2b")
    p = pub.publish(db, payload([job("1"), job("2")]), now="t3")
    assert p.reopened == 1 and rows(db)["ashby:acme:2"]["status"] == "open"
    assert rows(db)["ashby:acme:2"]["first_seen_at"] == "t1"


def test_extractor_version_bump_reclassifies(db, monkeypatch):
    pub.publish(db, payload([job("1")]), now="t1")
    monkeypatch.setattr(pub, "EXTRACT_VERSION", pub.EXTRACT_VERSION + 1)
    p = pub.publish(db, payload([job("1", level="maybe")]), now="t2")
    assert p.reclassified == 1 and rows(db)["ashby:acme:1"]["level"] == "maybe"


def test_runs_are_recorded(db):
    pub.publish(db, payload([job("1")], errors={"X": "HTTP 429"}), now="t1")
    run = db.query("SELECT * FROM runs")[0]
    assert (run["jobs_new"], run["companies_failed"], json.loads(run["errors"])) == (1, 1, {"X": "HTTP 429"})


@pytest.mark.parametrize("value,expected", [
    (None, "NULL"), (True, "1"), (3, "3"), (0.5, "0.5"),
    ("it's", "'it''s'"), (["a"], "'[\"a\"]'"), ("nul\x00l", "'null'"),
])
def test_sql_literal(value, expected):
    assert pub.sql_literal(value) == expected


def test_quotes_in_text_survive_round_trip(db):
    pub.publish(db, payload([job("1", title="Engineer, O'Reilly's team", desc="It's '; DROP TABLE jobs; --")]), now="t1")
    r = rows(db)["ashby:acme:1"]
    assert r["title"] == "Engineer, O'Reilly's team" and r["description_text"].startswith("It's '; DROP")


def test_huge_description_is_capped_under_d1_statement_limit(db):
    p = pub.publish(db, payload([job("1", desc="x" * 200_000, content="0" * 64)]), now="t1")
    assert len(p.sql.encode()) < 100_000
    assert len(rows(db)["ashby:acme:1"]["description_text"]) == pub.MAX_DESCRIPTION_CHARS


def test_rule_change_rewrites_only_jobs_whose_results_changed(db, monkeypatch):
    pub.publish(db, payload([job("1"), job("2")]), now="t1")
    monkeypatch.setattr(pub, "EXTRACT_VERSION", pub.EXTRACT_VERSION + 1)
    # Job 1's result is unchanged by the "new rules"; job 2's level moves.
    p = pub.publish(db, payload([job("1"), job("2", level="maybe")]), now="t2")
    assert p.reclassified == 1 and "ashby:acme:1" not in p.sql
    assert rows(db)["ashby:acme:2"]["level"] == "maybe"


def test_legacy_rows_without_extract_hash_fall_back_to_version(db, monkeypatch):
    pub.publish(db, payload([job("1")]), now="t1")
    db.execute_script("UPDATE jobs SET extract_hash = NULL;")
    assert pub.publish(db, payload([job("1")]), now="t2").sql == ""  # same version: left alone
    monkeypatch.setattr(pub, "EXTRACT_VERSION", pub.EXTRACT_VERSION + 1)
    p = pub.publish(db, payload([job("1")]), now="t3")
    assert p.reclassified == 1 and rows(db)["ashby:acme:1"]["extract_hash"]


def test_write_budget_puts_new_jobs_first_and_defers_the_rest(db):
    pub.publish(db, payload([job("1"), job("2")]), now="t1")
    # Next run: job 1 changed, jobs 3 and 4 are new, job 2 vanished. Budget fits two indexed writes.
    p = pub.plan([job("1", desc="new text"), job("3"), job("4")], [{"source": "ashby", "company_slug": "acme"}],
                 db.query("SELECT * FROM jobs"), "t2", budget=4)
    assert (p.new, p.changed, p.missed, p.deferred) == (2, 0, 0, 2)
    assert p.rows_written == 4
