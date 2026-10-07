"""Adapters against real API responses saved in tests/fixtures/sources/."""

import json
from pathlib import Path

import pytest

from sources import ADAPTERS, ashby, greenhouse, lever
from sources.models import Company, Job
from sources.text import html_to_text

FIXTURES = Path(__file__).parent / "fixtures" / "sources"


def load(name):
    return json.loads((FIXTURES / name).read_text())


HUME = Company("Hume AI", "greenhouse", "humeai")
CRED = Company("CRED", "lever", "cred")
PINECONE = Company("Pinecone", "ashby", "pinecone")


@pytest.mark.parametrize("module,fixture,company,count", [
    (greenhouse, "greenhouse_humeai.json", HUME, 5),
    (lever, "lever_cred.json", CRED, 8),
    (ashby, "ashby_pinecone.json", PINECONE, 5),
])
def test_every_posting_is_normalized(module, fixture, company, count):
    jobs = module.parse(load(fixture), company)
    assert len(jobs) == count
    for job in jobs:
        assert job.source == module.NAME
        assert job.id == f"{module.NAME}:{company.slug}:{job.external_id}"
        assert job.company == company.name
        assert job.title and job.url.startswith("https://")
        assert job.description_text, f"empty description for {job.title}"
        assert "<" not in job.description_text and "&lt;" not in job.description_text
        assert job.posted_at and job.posted_at.endswith("Z")
        assert len(job.content_hash) == 64
    assert len({j.id for j in jobs}) == count


def test_registry_has_every_adapter():
    assert set(ADAPTERS) == {"greenhouse", "lever", "ashby", "workday", "darwinbox", "keka", "zoho_recruit", "amazon", "eightfold", "hn"}


def test_greenhouse_fields():
    job = next(j for j in greenhouse.parse(load("greenhouse_humeai.json"), HUME) if j.external_id == "4775962008")
    assert job.title == "AI Researcher"
    assert job.location_raw == "NYC, San Jose, or Remote"
    assert job.url == "https://job-boards.greenhouse.io/humeai/jobs/4775962008"
    assert job.posted_at == "2025-06-20T15:52:49Z"  # first_published, converted from -04:00
    # The YoE requirement must survive HTML stripping, on its own line, for the extractor.
    assert "- 2+ years of experience contributing to the training" in job.description_text


def test_lever_requirements_in_lists_are_kept():
    jobs = lever.parse(load("lever_cred.json"), CRED)
    job = next(j for j in jobs if j.title == "accounts payable manager")
    assert job.location_raw == "hyderabad"
    assert job.ats_workplace_type == "onsite"
    assert job.ats_countries == ["IN"]
    assert job.employment_type == "full time"
    # CRED puts the whole body in lists[], with descriptionPlain empty.
    assert "Finance Manager" in job.description_text
    assert job.posted_at.startswith("2026-")


def test_ashby_fields():
    jobs = ashby.parse(load("ashby_pinecone.json"), PINECONE)
    job = next(j for j in jobs if j.title == "Associate Field Engineer")
    assert job.ats_workplace_type == "onsite"
    assert job.ats_countries == ["USA"]
    assert job.employment_type == "FullTime"
    assert "entry level role for new grads" in job.description_text
    remote = next(j for j in jobs if j.location_raw == "US Remote")
    assert remote.ats_workplace_type == "remote"


def test_ashby_skips_unlisted():
    payload = load("ashby_pinecone.json")
    payload["jobs"][0]["isListed"] = False
    assert len(ashby.parse(payload, PINECONE)) == 4


@pytest.mark.parametrize("module", [greenhouse, lever, ashby])
def test_missing_board_yields_no_jobs(module):
    assert module.parse(None, Company("X", module.NAME, "x")) == []


def test_content_hash_changes_with_description():
    a = Job("lever", "1", "C", "c", "T", "https://x", "Remote", "needs 2+ years")
    b = Job("lever", "1", "C", "c", "T", "https://x", "Remote", "needs 3+ years")
    assert a.content_hash != b.content_hash
    assert a.dedupe_key == b.dedupe_key


def test_html_to_text_keeps_structure():
    text = html_to_text("<p>Intro</p><ul><li><p>3+ years Python</p></li><li>PyTorch</li></ul><p>a&nbsp;b</p>")
    assert text.splitlines() == ["Intro", "- 3+ years Python", "- PyTorch", "a b"]


def test_html_to_text_handles_greenhouse_double_encoding():
    assert html_to_text("&lt;p&gt;Hello &amp;amp; bye&lt;/p&gt;") == "Hello & bye"
