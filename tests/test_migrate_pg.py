"""D1 -> Postgres migration: row conversion and paging (the Postgres writes are checked by hand
against a local Postgres; see the PR)."""

from datetime import datetime, timezone

import migrate_d1_to_pg as m
from publish_d1 import SqliteDatabase


def d1_row(**over):
    row = {
        "id": "greenhouse:acme:1", "source": "greenhouse", "company": "Acme", "title": "ML Engineer",
        "url": "https://x/1", "location_raw": "Pune, India", "department": None, "employment_type": None,
        "posted_at": "2026-10-01T05:00:00Z", "first_seen_at": "2026-10-02T00:00:00Z", "status": "open",
        "missed_runs": 0, "description_text": "0-1 years", "content_hash": "h", "extract_version": 4,
        "level": "fresher", "level_confidence": 0.9, "level_reason": "0-1 years", "yoe_min": 0, "yoe_max": 1,
        "yoe_evidence": "0-1 years", "batch_years": "[2026]", "role_match": 1, "role_family": "ai_ml",
        "location_type": None, "countries": '["India"]', "cities": '["Pune"]', "eligible": 1,
        "visa_sponsorship": "unknown", "skills": None, "evidence": '{"level": []}', "extract_hash": "x",
    }
    return {**row, **over}


def test_job_row_parses_times_and_keeps_first_seen():
    row = m.job_row(d1_row(), company_id=7)
    assert row["company_id"] == 7 and row["status"] == "open"
    assert row["posted_at"] == datetime(2026, 10, 1, 5, tzinfo=timezone.utc)
    assert row["first_seen_at"] == datetime(2026, 10, 2, tzinfo=timezone.utc)
    assert m.job_row(d1_row(posted_at="Sat Oct 03"), 1)["posted_at"] is None  # unparseable -> NULL


def test_label_row_turns_json_text_into_arrays_and_flags():
    row = m.label_row(d1_row())
    assert row["rules_version"] == 4 and row["label_hash"] == "x"
    assert (row["countries"], row["cities"], row["batch_years"]) == (["India"], ["Pune"], [2026])
    assert row["role_match"] is True and row["eligible"] is True and row["evidence"].obj == {"level": []}


def test_label_row_drops_values_the_schema_would_reject():
    row = m.label_row(d1_row(location_type="None", visa_sponsorship="maybe", countries="not json",
                             extract_hash=None))
    assert row["location_type"] is None and row["visa_sponsorship"] == "unknown" and row["countries"] == []
    assert len(row["label_hash"]) == 64  # computed when D1 had none


def test_pages_cover_every_row_once(tmp_path, monkeypatch):
    db = SqliteDatabase(tmp_path / "d1.db")
    db.execute_script("CREATE TABLE jobs (id TEXT PRIMARY KEY);"
                      + "".join(f"INSERT INTO jobs VALUES ('lever:o''brien:{i:03}');" for i in range(23)))
    monkeypatch.setattr(m, "BATCH", 5)
    pages = list(m.d1_pages(db))
    assert [len(p) for p in pages] == [5, 5, 5, 5, 3]
    assert len({r["id"] for p in pages for r in p}) == 23  # a quote in the id doesn't break paging


def test_differences_names_each_mismatch():
    from collections import Counter
    src = {"status": Counter(open=3), "level": Counter(fresher=1), "company": Counter(Acme=3)}
    dst = {"status": Counter(open=2), "level": Counter(fresher=1), "company": Counter(Acme=2)}
    assert m.differences(src, dst) == ["status 'open': D1 3, Postgres 2", "company 'Acme': D1 3, Postgres 2"]
