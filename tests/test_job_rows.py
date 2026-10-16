"""Fetched job -> stored rows: label conversion and the change fingerprint."""

import job_rows as jr


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


def test_label_row_turns_json_text_into_arrays_and_flags():
    row = jr.label_row(d1_row())
    assert row["rules_version"] == 4 and row["label_hash"] == "x"
    assert (row["countries"], row["cities"], row["batch_years"]) == (["India"], ["Pune"], [2026])
    assert row["role_match"] is True and row["eligible"] is True and row["evidence"].obj == {"level": []}


def test_label_row_drops_values_the_schema_would_reject():
    row = jr.label_row(d1_row(location_type="None", visa_sponsorship="maybe", countries="not json",
                             extract_hash=None))
    assert row["location_type"] is None and row["visa_sponsorship"] == "unknown" and row["countries"] == []
    assert len(row["label_hash"]) == 64  # computed when the row came without one


def test_label_row_takes_pipeline_lists_as_well_as_json_text():
    row = jr.label_row(d1_row(countries=["India"], batch_years=[2026], evidence={"level": []}))
    assert (row["countries"], row["batch_years"], row["evidence"].obj) == (["India"], [2026], {"level": []})


def test_extract_hash_changes_only_with_extracted_values():
    base = jr.to_row({**d1_row(), "company_slug": "acme", "reason": "0-1 years", "evidence": [],
                      "countries": ["India"], "cities": [], "batch_years": [2026]})
    same = jr.to_row({**d1_row(), "company_slug": "acme", "reason": "0-1 years", "evidence": [],
                      "countries": ["India"], "cities": [], "batch_years": [2026], "url": "https://other"})
    relabelled = jr.to_row({**d1_row(), "company_slug": "acme", "reason": "0-1 years", "evidence": [],
                            "countries": ["India"], "cities": [], "batch_years": [2026], "level": "maybe"})
    assert base["extract_hash"] == same["extract_hash"] != relabelled["extract_hash"]
