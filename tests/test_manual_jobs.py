"""Jobs added by hand (/admin) become the "manual" source and are labelled like any job."""

import os
from datetime import datetime, timezone

import psycopg
import pytest

from sources import manual

PG = os.environ.get("PG_TEST_URL")

ROW = {"id": 7, "company": "Acme AI", "title": "ML Engineer - New Grad", "url": "https://acme.ai/careers/ml",
       "location_raw": "Bengaluru, India", "description_text": "Freshers welcome. Python, PyTorch.",
       "posted_at": datetime(2026, 11, 10, tzinfo=timezone.utc)}


def test_row_becomes_a_job_with_a_stable_id():
    job = manual.to_job(ROW)
    assert job.id == "manual:acme-ai:7"
    assert (job.company, job.title, job.url, job.location_raw) == ("Acme AI", ROW["title"], ROW["url"], "Bengaluru, India")
    assert job.posted_at == "2026-11-10T00:00:00Z"


def test_company_slug_is_lowercase_words():
    assert manual.slug("  Zoho Corp. (India) ") == "zoho-corp-india"


@pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")
def test_load_reads_open_rows_and_names_every_company_as_a_board():
    from test_api import reset
    reset()
    with psycopg.connect(PG, autocommit=True) as conn:
        for company, closed in (("Acme AI", None), ("Beta", None), ("Gone Co", datetime.now(timezone.utc))):
            conn.execute("INSERT INTO manual_jobs (company, title, url, description_text, closed_at) "
                         "VALUES (%s, 'Engineer', 'https://x.example/j', 'Build things.', %s)", (company, closed))
    jobs, boards = manual.load(PG)
    assert sorted(j.company for j in jobs) == ["Acme AI", "Beta"]
    # A company whose last manual job closed is still a board that answered, so its job closes.
    assert {"source": "manual", "company_slug": "gone-co"} in boards
    assert len(boards) == 3
