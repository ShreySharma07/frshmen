"""API against Postgres (the schema in db/postgres/), filled by the real Supabase publish path
from fixture postings. Needs PG_TEST_URL (CI starts a Postgres service); skipped without it."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

import publish_pg as pub
from extract.classify import classify
from extract.profile import load_profile
from extract.stored_text import compact
from extract.role import match_role
from jobs_api import create_app
from sources import ashby, greenhouse, lever
from sources.models import Company

FIX = "tests/fixtures/sources/"
PG = os.environ.get("PG_TEST_URL")
pytestmark = pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")
# Supabase provides the auth schema; tests stand in for it.
AUTH_STUB = ("CREATE SCHEMA auth; CREATE TABLE auth.users (id uuid PRIMARY KEY); "
             "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS 'SELECT NULL::uuid';")


def records():
    profile = load_profile()
    jobs = (greenhouse.parse(json.load(open(FIX + "greenhouse_humeai.json")), Company("Hume AI", "greenhouse", "humeai"))
            + lever.parse(json.load(open(FIX + "lever_cred.json")), Company("CRED", "lever", "cred"))
            + ashby.parse(json.load(open(FIX + "ashby_pinecone.json")), Company("Pinecone", "ashby", "pinecone")))
    # Fixture postings are months old; age has its own test, so these carry no posting date.
    out = []
    for j in jobs:
        label = classify(j.title, j.description_text)
        # Stored as the pipeline stores it (scripts/fetch_jobs.py): the compact text.
        out.append({**j.to_dict(), **label.to_dict(), **match_role(j.title, j.description_text, profile).to_dict(),
                    "posted_at": None, "description_text": compact(j.description_text, label.evidence)})
    return out


def iso(dt):
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def reset(migrate=True):
    """Empty database with the current schema, like Supabase after the migrations workflow."""
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA public")
        conn.execute(AUTH_STUB)
        if migrate:
            for f in sorted(Path("db/postgres").glob("*.sql")):
                conn.execute(f.read_text())


def publish(jobs, now):
    with psycopg.connect(PG, autocommit=True) as conn:
        pub.publish(conn, {"jobs": jobs, "boards_ok": [], "errors": {}}, now=now)


def app_client():
    app = create_app()
    app.state.dsn = PG
    return TestClient(app)


@pytest.fixture
def client():
    reset()
    recs = records()
    # A synthetic target fresher, first seen now, plus one seen 3 days ago.
    fresh = dict(recs[0], posted_at=None, id="ashby:acme:new", title="ML Engineer - New Grad", company="Acme", company_slug="acme",
                 source="ashby", level="fresher", role_match=True, role_family="ai_ml", content_hash="x1",
                 countries=["India"], cities=["Bengaluru", "Pune"])
    old = dict(fresh, id="ashby:acme:old", title="ML Engineer, Fresher", content_hash="x2",
               countries=["United States", "Canada"], cities=[])
    publish([old], datetime.now(timezone.utc) - timedelta(days=3))
    publish([*recs, fresh, old], datetime.now(timezone.utc))
    return app_client()


def test_default_lists_every_open_job_newest_first(client):
    body = client.get("/api/jobs?per_page=50").json()
    assert len(body["jobs"]) == 20 and not body["has_more"]  # 18 fixture postings + 2 synthetic, all roles and levels
    assert {j["level"] for j in body["jobs"]} >= {"fresher", "experienced"}
    assert body["jobs"][-1]["title"] == "ML Engineer, Fresher"  # first seen 3 days ago, no posting date
    assert "description_text" not in body["jobs"][0]  # list stays light; detail endpoint has it


def test_pages_and_total_counted_on_request(client):
    assert client.get("/api/jobs").json()["per_page"] == 20
    first = client.get("/api/jobs?per_page=15&with_total=true").json()
    second = client.get("/api/jobs?per_page=15&page=2").json()
    assert (len(first["jobs"]), first["total"], first["pages"]) == (15, 20, 2)
    assert first["has_more"] and len(second["jobs"]) == 5 and "total" not in second
    assert not {j["id"] for j in first["jobs"]} & {j["id"] for j in second["jobs"]}


def test_new_in_24h_uses_first_seen(client):
    titles = {j["title"] for j in client.get("/api/jobs?posted=24h&experience=fresher").json()["jobs"]}
    assert "ML Engineer - New Grad" in titles and "ML Engineer, Fresher" not in titles  # first seen 3 days ago


def test_role_scope(client):
    everything = client.get("/api/jobs?per_page=50").json()["jobs"]
    target = client.get("/api/jobs?role=target&per_page=50").json()["jobs"]
    assert 0 < len(target) < len(everything) and all(j["role_family"] for j in target)


def test_search_and_company_filter(client):
    assert {j["company"] for j in client.get("/api/jobs?q=pinecone").json()["jobs"]} == {"Pinecone"}
    assert {j["company"] for j in client.get("/api/jobs?company=CRED").json()["jobs"]} == {"CRED"}


def test_detail_has_description_and_parsed_evidence(client):
    job = client.get("/api/jobs/greenhouse:humeai:4775962008").json()
    assert job["level"] == "experienced" and "2+ years" in job["description_text"]
    assert isinstance(job["evidence"]["level"], list) and job["evidence"]["level"]
    assert job["role_match"] is True


def test_detail_404(client):
    assert client.get("/api/jobs/nope").status_code == 404


def test_meta_comes_from_the_snapshot_publish_writes(client):
    meta = client.get("/api/meta").json()
    assert meta["total"] == 20 and meta["levels"]["fresher"] == 3 and meta["snapshot_at"]
    assert {"company": "Acme", "n": 2} in meta["companies"]
    assert meta["last_run"]["jobs_new"] >= 1 and meta["fit_check"] is False
    assert isinstance(meta["visa_or_relocation"], int)


def test_meta_is_computed_live_before_the_first_snapshot(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("DELETE FROM meta")
    meta = client.get("/api/meta").json()
    assert meta["total"] == 20 and meta["snapshot_at"] is None


def test_rejects_bad_params(client):
    assert client.get("/api/jobs?experience=bogus").status_code == 422
    assert client.get("/api/jobs?per_page=1000").status_code == 422
    assert client.get("/api/jobs?page=0").status_code == 422


def test_list_carries_one_highlight_not_full_evidence(client):
    jobs = client.get("/api/jobs?per_page=50").json()["jobs"]
    hume = next(j for j in jobs if j["id"] == "greenhouse:humeai:4775962008")
    assert "evidence" not in hume
    assert hume["highlight"]["kind"] == "yoe_required" and "2+ years" in hume["highlight"]["text"]
    pinecone = next(j for j in jobs if j["title"] == "Associate Field Engineer")
    assert pinecone["highlight"] == {"kind": "fresher_text",
                                     "text": "This is intended to be an entry level role for new grads/early career professionals."}


def test_unexpected_errors_return_json_with_cause():
    reset(migrate=False)  # no tables: every query fails
    app = create_app()
    app.state.dsn = PG
    body = TestClient(app, raise_server_exceptions=False).get("/api/meta")
    assert body.status_code == 500 and body.json()["error"].startswith("UndefinedTableError")


def test_reposted_listing_link_opens_the_original_job(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("INSERT INTO job_aliases VALUES ('ashby:acme:relisted', 'ashby:acme:new')")
    assert client.get("/api/jobs/ashby:acme:relisted").json()["id"] == "ashby:acme:new"


def test_country_filter_matches_whole_names(client):
    india = [j["title"] for j in client.get("/api/jobs?country=India&experience=fresher").json()["jobs"]]
    canada = [j["title"] for j in client.get("/api/jobs?country=Canada&experience=fresher").json()["jobs"]]
    assert india == ["ML Engineer - New Grad"] and canada == ["ML Engineer, Fresher"]
    assert client.get("/api/jobs?country=Ind").json()["jobs"] == []


def test_meta_lists_countries_with_counts(client):
    countries = {c["country"]: c["n"] for c in client.get("/api/meta").json()["countries"]}
    assert countries["India"] >= 1 and countries["Canada"] >= 1


def test_city_filter_and_meta_cities(client):
    pune = [j["title"] for j in client.get("/api/jobs?country=India&city=Pune&experience=fresher").json()["jobs"]]
    assert pune == ["ML Engineer - New Grad"]
    assert client.get("/api/jobs?city=Mumbai").json()["jobs"] == []
    cities = {c["city"]: c["n"] for c in client.get("/api/meta").json()["cities"]}
    assert cities["Bengaluru"] >= 1 and cities["Pune"] == 1


@pytest.fixture
def mixed():
    reset()
    base = dict(records()[0], posted_at=None, source="ashby", company="Acme", company_slug="acme", level="fresher", role_match=True,
                countries=["India"], cities=["Pune"])
    rows = [
        dict(base, id="ashby:acme:ml", title="ML Engineer", role_family="ai_ml", content_hash="m1"),
        dict(base, id="ashby:acme:swe", title="Software Engineer", role_family="generic_swe", content_hash="m2"),
        dict(base, id="ashby:acme:and", title="Android Developer", role_family="mobile", content_hash="m3"),
        dict(base, id="ashby:acme:us", title="ML Engineer (US)", role_family="ai_ml", content_hash="m4",
             countries=["United States"], cities=[], eligible=False,
             eligibility_reason="United States without visa sponsorship"),
    ]
    publish(rows, datetime.now(timezone.utc))
    return app_client()


def test_location_rules_are_an_opt_in_filter(mixed):
    assert "ML Engineer (US)" in {j["title"] for j in mixed.get("/api/jobs").json()["jobs"]}
    mine = {j["title"] for j in mixed.get("/api/jobs?eligible_only=true").json()["jobs"]}
    assert "ML Engineer (US)" not in mine and len(mine) == 3
    assert mixed.get("/api/meta").json()["levels"]["fresher"] == 4


def test_family_filter_groups_generic_swe_with_ai_ml(mixed):
    ai = {j["title"] for j in mixed.get("/api/jobs?role=ai_ml&eligible_only=true").json()["jobs"]}
    mobile = [j["title"] for j in mixed.get("/api/jobs?role=mobile").json()["jobs"]]
    assert ai == {"ML Engineer", "Software Engineer"} and mobile == ["Android Developer"]
    assert mixed.get("/api/meta").json()["roles"] == {"target": 4, "ai_ml": 3, "backend": 0, "mobile": 1}


@pytest.fixture
def by_yoe():
    reset()
    base = dict(records()[0], posted_at=None, source="ashby", company="Acme", company_slug="acme", role_match=True, role_family="ai_ml",
                countries=["India"], cities=["Pune"])
    rows = [
        dict(base, id="ashby:acme:f", title="Fresher", level="fresher", yoe_min=None, yoe_max=None, content_hash="y1"),
        dict(base, id="ashby:acme:1", title="One year", level="maybe", yoe_min=1, yoe_max=2, content_hash="y2"),
        dict(base, id="ashby:acme:2", title="Two years", level="experienced", yoe_min=2, yoe_max=5, content_hash="y3"),
        dict(base, id="ashby:acme:5", title="Five years", level="experienced", yoe_min=5, yoe_max=None, content_hash="y4"),
        dict(base, id="ashby:acme:u", title="Unstated", level="maybe", yoe_min=None, yoe_max=None, content_hash="y5"),
        dict(base, id="ashby:acme:i", title="ML Intern", level="maybe", yoe_min=3, yoe_max=None, content_hash="y6"),
        dict(base, id="ashby:acme:t", title="Internal Tools Engineer", level="experienced", yoe_min=3, yoe_max=None,
             content_hash="y7"),
        dict(base, id="ashby:acme:d", title="Data Science Trainee", level="maybe", yoe_min=4, yoe_max=None,
             content_hash="y8"),
        # Experienced from a senior title, no number: "Not stated" in years, but never shown to juniors.
        dict(base, id="ashby:acme:s", title="Senior ML Engineer", level="experienced", yoe_min=None, yoe_max=None,
             content_hash="y9"),
    ]
    publish(rows, datetime.now(timezone.utc))
    return app_client()


@pytest.mark.parametrize("bucket,titles", [
    ("fresher", {"Fresher"}),
    ("0-0", {"Fresher"}),
    ("0-1", {"Fresher", "One year"}),
    ("0-2", {"Fresher", "One year", "Two years"}),
    ("0-5", {"Fresher", "One year", "Two years", "Five years", "ML Intern", "Internal Tools Engineer",
             "Data Science Trainee"}),
    ("0-4", {"Fresher", "One year", "Two years", "ML Intern", "Internal Tools Engineer", "Data Science Trainee"}),
    ("unstated", {"Unstated", "Senior ML Engineer"}),
    ("experienced", {"Two years", "Five years", "Internal Tools Engineer", "Senior ML Engineer"}),
    ("internship", {"ML Intern", "Data Science Trainee"}),
    ("all", {"Fresher", "One year", "Two years", "Five years", "Unstated", "ML Intern", "Internal Tools Engineer",
             "Data Science Trainee", "Senior ML Engineer"}),
])
def test_experience_buckets(by_yoe, bucket, titles):
    got = {j["title"] for j in by_yoe.get(f"/api/jobs?experience={bucket}").json()["jobs"]}
    assert got == titles


def test_include_unstated_adds_maybe_jobs_without_years_but_never_senior_ones(by_yoe):
    got = {j["title"] for j in by_yoe.get("/api/jobs?experience=0-1&include_unstated=true").json()["jobs"]}
    assert got == {"Fresher", "One year", "Unstated"}


def test_old_postings_stay_listed_unless_filtered_and_newest_posting_sorts_first():
    reset()
    now = datetime.now(timezone.utc)
    base = dict(records()[0], source="ashby", company="Acme", company_slug="acme", level="fresher", role_match=True,
                role_family="ai_ml", countries=["India"], cities=[])
    rows = [
        dict(base, id="ashby:acme:old", title="Old", posted_at=iso(now - timedelta(days=45)), content_hash="a1"),
        dict(base, id="ashby:acme:recent", title="Recent", posted_at=iso(now - timedelta(days=3)), content_hash="a2"),
        dict(base, id="ashby:acme:newest", title="Newest", posted_at=iso(now - timedelta(hours=2)), content_hash="a3"),
        dict(base, id="ashby:acme:undated", title="Undated", posted_at=None, content_hash="a4"),
    ]
    publish(rows, now - timedelta(days=5))
    c = app_client()
    titles = [j["title"] for j in c.get("/api/jobs").json()["jobs"]]
    assert titles == ["Newest", "Recent", "Undated", "Old"]  # undated jobs sort by first-seen time (5 days ago)
    assert [j["title"] for j in c.get("/api/jobs?posted=30d").json()["jobs"]] == ["Newest", "Recent", "Undated"]
    assert [j["title"] for j in c.get("/api/jobs?posted=7d").json()["jobs"]] == ["Newest", "Recent", "Undated"]


RESUME = "B.Tech CS (AI), 2026. Python, PyTorch, FastAPI. Built a multi-agent LLM system and a RAG pipeline."
HUME = "greenhouse:humeai:4775962008"


def test_fit_check_is_off_by_default(client):
    assert client.post(f"/api/jobs/{HUME}/fit", json={"resume": RESUME}).status_code == 404
    assert client.get("/api/meta").json()["fit_check"] is False


def gemini_reply(payload):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


def test_fit_check_when_switched_on(client):
    calls = []

    async def post(url, headers, body):
        calls.append((url, headers, json.loads(body)))
        if "3.5" in url:
            return 404, {"error": {"message": "not found"}}
        return 200, gemini_reply({"fit": "weak", "score": 140, "matched": ["Python"], "missing": ["2+ years"],
                                  "experience": "Asks for 2+ years; resume shows none.", "advice": "Apply to new-grad roles."})

    client.app.state.fit = ("secret-key", post)
    res = client.post(f"/api/jobs/{HUME}/fit", json={"resume": RESUME})
    assert res.status_code == 200
    body = res.json()
    assert body["fit"] == "weak" and body["score"] == 100 and body["model"] == "gemini-3.1-flash-lite"
    url, headers, sent = calls[-1]
    assert "key=" not in url and headers["x-goog-api-key"] == "secret-key"
    prompt = sent["contents"][0]["parts"][0]["text"]
    assert RESUME in prompt and "2+ years" in prompt  # the job's own description goes in
    assert client.get("/api/meta").json()["fit_check"] is True


def test_fit_check_errors(client):
    async def quota(url, headers, body):
        return 429, {}

    client.app.state.fit = ("k", quota)
    assert client.post(f"/api/jobs/{HUME}/fit", json={"resume": RESUME}).status_code == 503
    assert client.post("/api/jobs/nope/fit", json={"resume": RESUME}).status_code == 404
    assert client.post(f"/api/jobs/{HUME}/fit", json={"resume": "too short"}).status_code == 422


def test_salary_shows_on_the_list_and_the_job(client):
    """Hume AI's postings state a pay band; the list reads it from the stored text's first line."""
    jobs = client.get("/api/jobs?per_page=50").json()["jobs"]
    paid = [j for j in jobs if j["salary"]]
    assert any(j["company"] == "Hume AI" for j in paid)  # (the synthetic "Acme" rows copy Hume postings)
    assert all(j["salary"] is None for j in jobs if j["company"] == "CRED")
    detail = client.get(f"/api/jobs/{paid[0]['id']}").json()
    assert detail["salary"] == paid[0]["salary"]
    assert detail["description_text"].startswith(f"Salary\n{paid[0]['salary']}\n")
