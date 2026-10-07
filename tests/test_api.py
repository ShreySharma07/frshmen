"""API against a SQLite database filled by the real publish path from fixture postings."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import publish_d1 as pub
from extract.classify import classify
from extract.profile import load_profile
from extract.role import match_role
from jobs_api import create_app
from sources import ashby, greenhouse, lever
from sources.models import Company
from storage import SqliteDatabase

FIX = "tests/fixtures/sources/"


def records():
    profile = load_profile()
    jobs = (greenhouse.parse(json.load(open(FIX + "greenhouse_humeai.json")), Company("Hume AI", "greenhouse", "humeai"))
            + lever.parse(json.load(open(FIX + "lever_cred.json")), Company("CRED", "lever", "cred"))
            + ashby.parse(json.load(open(FIX + "ashby_pinecone.json")), Company("Pinecone", "ashby", "pinecone")))
    # Fixture postings are months old; age has its own test, so these carry no posting date.
    return [{**j.to_dict(), **classify(j.title, j.description_text).to_dict(),
             **match_role(j.title, j.description_text, profile).to_dict(), "posted_at": None} for j in jobs]


def iso(dt):
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "jobs.db"
    db = pub.SqliteDatabase(path)
    recs = records()
    # A synthetic target fresher, first seen now, plus one seen 3 days ago.
    fresh = dict(recs[0], posted_at=None, id="ashby:acme:new", title="ML Engineer - New Grad", company="Acme", company_slug="acme",
                 source="ashby", level="fresher", role_match=True, role_family="ai_ml", content_hash="x1",
                 countries=["India"], cities=["Bengaluru", "Pune"])
    old = dict(fresh, id="ashby:acme:old", title="ML Engineer, Fresher", content_hash="x2",
               countries=["United States", "Canada"], cities=[])
    pub.publish(db, {"jobs": [old], "boards_ok": [], "errors": {}}, now=iso(datetime.now(timezone.utc) - timedelta(days=3)))
    pub.publish(db, {"jobs": [*recs, fresh, old], "boards_ok": [], "errors": {}}, now=iso(datetime.now(timezone.utc)))
    app = create_app()
    app.state.db = SqliteDatabase(str(path))
    return TestClient(app)


def test_default_view_is_open_target_freshers_newest_first(client):
    body = client.get("/api/jobs").json()
    titles = [j["title"] for j in body["jobs"]]
    assert titles == ["ML Engineer - New Grad", "ML Engineer, Fresher"]
    assert all(j["level"] == "fresher" for j in body["jobs"])
    assert "description_text" not in body["jobs"][0]  # list stays light; detail endpoint has it


def test_new_view_uses_first_seen_within_24h(client):
    titles = [j["title"] for j in client.get("/api/jobs?view=new").json()["jobs"]]
    assert titles == ["ML Engineer - New Grad"]


def test_all_roles_includes_non_targets(client):
    target = client.get("/api/jobs?view=all").json()["jobs"]
    everything = client.get("/api/jobs?view=all&role=all").json()["jobs"]
    assert len(everything) == 20 and len(target) < len(everything)


def test_search_and_company_filter(client):
    assert {j["company"] for j in client.get("/api/jobs?view=all&role=all&q=pinecone").json()["jobs"]} == {"Pinecone"}
    assert {j["company"] for j in client.get("/api/jobs?view=all&role=all&company=CRED").json()["jobs"]} == {"CRED"}


def test_pagination(client):
    first = client.get("/api/jobs?view=all&role=all&limit=5").json()
    second = client.get("/api/jobs?view=all&role=all&limit=5&offset=5").json()
    assert first["has_more"] and len(first["jobs"]) == 5
    assert not {j["id"] for j in first["jobs"]} & {j["id"] for j in second["jobs"]}


def test_detail_has_description_and_parsed_evidence(client):
    job = client.get("/api/jobs/greenhouse:humeai:4775962008").json()
    assert job["level"] == "experienced" and "2+ years" in job["description_text"]
    assert isinstance(job["evidence"]["level"], list) and job["evidence"]["level"]
    assert job["role_match"] is True


def test_detail_404(client):
    assert client.get("/api/jobs/nope").status_code == 404


def test_meta_counts(client):
    meta = client.get("/api/meta").json()
    assert meta["counts"]["fresher"] == 2 and meta["counts"]["new"] >= 1
    assert {"company": "Acme", "n": 2} in meta["companies"]
    assert meta["last_run"]["jobs_new"] >= 1


def test_rejects_bad_params(client):
    assert client.get("/api/jobs?view=bogus").status_code == 422
    assert client.get("/api/jobs?limit=1000").status_code == 422


def test_list_carries_one_highlight_not_full_evidence(client):
    jobs = client.get("/api/jobs?view=all&role=all").json()["jobs"]
    hume = next(j for j in jobs if j["id"] == "greenhouse:humeai:4775962008")
    assert "evidence" not in hume
    assert hume["highlight"]["kind"] == "yoe_required" and "2+ years" in hume["highlight"]["text"]
    pinecone = next(j for j in jobs if j["title"] == "Associate Field Engineer")
    assert pinecone["highlight"] == {"kind": "fresher_text",
                                     "text": "This is intended to be an entry level role for new grads/early career professionals."}


def test_unexpected_errors_return_json_with_cause(tmp_path):
    from storage import SqliteDatabase as S

    app = create_app()
    app.state.db = S(str(tmp_path / "empty.db"))  # no tables: every query fails
    body = TestClient(app, raise_server_exceptions=False).get("/api/meta")
    assert body.status_code == 500 and body.json()["error"].startswith("OperationalError: no such table")


def test_country_filter_matches_whole_names(client):
    india = [j["title"] for j in client.get("/api/jobs?country=India").json()["jobs"]]
    canada = [j["title"] for j in client.get("/api/jobs?country=Canada").json()["jobs"]]
    assert india == ["ML Engineer - New Grad"] and canada == ["ML Engineer, Fresher"]
    assert client.get("/api/jobs?country=Ind").json()["jobs"] == []


def test_meta_lists_countries_with_counts(client):
    countries = {c["country"]: c["n"] for c in client.get("/api/meta").json()["countries"]}
    assert countries["India"] == 1 and countries["Canada"] == 1


def test_city_filter_and_meta_cities(client):
    pune = [j["title"] for j in client.get("/api/jobs?country=India&city=Pune").json()["jobs"]]
    assert pune == ["ML Engineer - New Grad"]
    assert client.get("/api/jobs?city=Mumbai").json()["jobs"] == []
    cities = {c["city"]: c["n"] for c in client.get("/api/meta").json()["cities"]}
    assert cities == {"Bengaluru": 1, "Pune": 1}


@pytest.fixture
def mixed(tmp_path):
    path = tmp_path / "mixed.db"
    db = pub.SqliteDatabase(path)
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
    pub.publish(db, {"jobs": rows, "boards_ok": [], "errors": {}}, now=iso(datetime.now(timezone.utc)))
    app = create_app()
    app.state.db = SqliteDatabase(str(path))
    return TestClient(app)


def test_ineligible_locations_are_hidden_unless_asked(mixed):
    titles = {j["title"] for j in mixed.get("/api/jobs").json()["jobs"]}
    assert "ML Engineer (US)" not in titles
    all_titles = {j["title"] for j in mixed.get("/api/jobs?include_ineligible=true").json()["jobs"]}
    assert "ML Engineer (US)" in all_titles
    assert mixed.get("/api/meta").json()["counts"]["fresher"] == 3


def test_family_filter_groups_generic_swe_with_ai_ml(mixed):
    ai = {j["title"] for j in mixed.get("/api/jobs?family=ai_ml").json()["jobs"]}
    mobile = [j["title"] for j in mixed.get("/api/jobs?family=mobile").json()["jobs"]]
    assert ai == {"ML Engineer", "Software Engineer"} and mobile == ["Android Developer"]
    assert mixed.get("/api/meta").json()["families"] == {"ai_ml": 2, "backend": 0, "mobile": 1}


def test_level_and_posted_filters_replace_view(client):
    both = [j["level"] for j in client.get("/api/jobs?level=any").json()["jobs"]]
    assert set(both) <= {"fresher", "maybe"} and "fresher" in both
    recent = [j["title"] for j in client.get("/api/jobs?level=fresher&posted=24h").json()["jobs"]]
    assert recent == ["ML Engineer - New Grad"]  # the 3-day-old fresher is filtered out
    assert client.get("/api/jobs?view=new").json() == client.get("/api/jobs?level=any&posted=24h").json()


@pytest.fixture
def by_yoe(tmp_path):
    path = tmp_path / "yoe.db"
    db = pub.SqliteDatabase(path)
    base = dict(records()[0], posted_at=None, source="ashby", company="Acme", company_slug="acme", role_match=True, role_family="ai_ml",
                countries=["India"], cities=["Pune"])
    rows = [
        dict(base, id="ashby:acme:f", title="Fresher", level="fresher", yoe_min=None, yoe_max=None, content_hash="y1"),
        dict(base, id="ashby:acme:1", title="One year", level="maybe", yoe_min=1, yoe_max=2, content_hash="y2"),
        dict(base, id="ashby:acme:2", title="Two years", level="experienced", yoe_min=2, yoe_max=5, content_hash="y3"),
        dict(base, id="ashby:acme:5", title="Five years", level="experienced", yoe_min=5, yoe_max=None, content_hash="y4"),
        dict(base, id="ashby:acme:u", title="Unstated", level="maybe", yoe_min=None, yoe_max=None, content_hash="y5"),
    ]
    pub.publish(db, {"jobs": rows, "boards_ok": [], "errors": {}}, now=iso(datetime.now(timezone.utc)))
    app = create_app()
    app.state.db = SqliteDatabase(str(path))
    return TestClient(app)


@pytest.mark.parametrize("bucket,titles", [
    ("fresher", {"Fresher"}),
    ("0-1", {"Fresher", "One year"}),
    ("0-2", {"Fresher", "One year", "Two years"}),
    ("0-5", {"Fresher", "One year", "Two years", "Five years"}),
    ("unstated", {"Unstated"}),
    ("all", {"Fresher", "One year", "Two years", "Five years", "Unstated"}),
])
def test_experience_buckets(by_yoe, bucket, titles):
    got = {j["title"] for j in by_yoe.get(f"/api/jobs?experience={bucket}").json()["jobs"]}
    assert got == titles


def test_postings_older_than_30_days_are_hidden_and_newest_posting_sorts_first(tmp_path):
    path = tmp_path / "age.db"
    db = pub.SqliteDatabase(path)
    now = datetime.now(timezone.utc)
    base = dict(records()[0], source="ashby", company="Acme", company_slug="acme", level="fresher", role_match=True,
                role_family="ai_ml", countries=["India"], cities=[])
    rows = [
        dict(base, id="ashby:acme:old", title="Old", posted_at=iso(now - timedelta(days=45)), content_hash="a1"),
        dict(base, id="ashby:acme:recent", title="Recent", posted_at=iso(now - timedelta(days=3)), content_hash="a2"),
        dict(base, id="ashby:acme:newest", title="Newest", posted_at=iso(now - timedelta(hours=2)), content_hash="a3"),
        dict(base, id="ashby:acme:undated", title="Undated", posted_at=None, content_hash="a4"),
    ]
    pub.publish(db, {"jobs": rows, "boards_ok": [], "errors": {}}, now=iso(now - timedelta(days=5)))
    app = create_app()
    app.state.db = SqliteDatabase(str(path))
    c = TestClient(app)
    titles = [j["title"] for j in c.get("/api/jobs").json()["jobs"]]
    assert titles == ["Newest", "Recent", "Undated"]  # undated jobs sort by first-seen time (5 days ago)
    assert c.get("/api/meta").json()["counts"]["fresher"] == 3
