"""/api/admin: only accounts listed in the admins table (db/postgres/0011_admins.sql) get in.
Needs PG_TEST_URL, like tests/test_api.py."""

from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from test_api import PG, app_client, publish, records, reset

pytestmark = pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")

ADMIN = "00000000-0000-4000-8000-0000000000ad"
STUDENT = "00000000-0000-4000-8000-00000000057d"
TOKENS = {"admin-token": ADMIN, "student-token": STUDENT}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_client():
    reset()
    now = datetime.now(timezone.utc)
    publish(records(), now)
    with psycopg.connect(PG, autocommit=True) as conn:
        for uid, name in ((ADMIN, "Shrey"), (STUDENT, "Asha")):
            conn.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
            conn.execute("INSERT INTO students (id, name) VALUES (%s, %s)", (uid, name))
        conn.execute("INSERT INTO admins (user_id) VALUES (%s)", (ADMIN,))
        conn.execute("INSERT INTO runs (finished_at, companies_ok, companies_failed, jobs_seen, jobs_new, jobs_changed, "
                     "jobs_closed, errors) VALUES (%s, 10, 1, 50, 5, 2, 1, '{\"Acme\": \"HTTP 500\"}')", (now,))
    client = app_client()

    async def verify(token):
        return TOKENS.get(token)

    client.app.state.auth = verify
    return client


def test_admin_needs_a_sign_in(admin_client):
    assert admin_client.get("/api/admin/overview").status_code == 401
    assert admin_client.get("/api/admin/overview", headers=bearer("forged")).status_code == 401


def test_signed_in_non_admin_is_refused(admin_client):
    assert admin_client.get("/api/admin/overview", headers=bearer("student-token")).status_code == 403


def test_overview_counts_jobs_pipeline_and_users(admin_client):
    res = admin_client.get("/api/admin/overview", headers=bearer("admin-token"))
    assert res.status_code == 200
    data = res.json()
    open_jobs = data["jobs"]["open"]
    assert open_jobs == len(records()) and open_jobs > 0
    assert data["jobs"]["new_24h"] == open_jobs  # all published just now
    assert sum(r["n"] for r in data["jobs"]["by_source"]) == open_jobs
    assert set(data["jobs"]["bands"]) == {"0-1", "1-3", "3-5", "5-8", "8+"}
    assert isinstance(data["jobs"]["by_category"], dict)
    run = data["pipeline"]["runs"][0]
    assert (run["companies_failed"], run["jobs_new"], run["error_count"]) == (1, 5, 1)
    assert data["pipeline"]["latest_errors"] == {"Acme": "HTTP 500"}
    assert data["users"]["total"] == 2
    assert data["users"]["signups"][-1]["n"] == 2  # both today
    assert data["users"]["usage_24h"] == {"fit_checks": 0, "tailored_resumes": 0}


def test_overview_is_not_cached_by_browsers_or_the_edge(admin_client):
    res = admin_client.get("/api/admin/overview", headers=bearer("admin-token"))
    assert "no-store" in res.headers.get("cache-control", "")


def test_overview_works_before_the_first_pipeline_run(admin_client):
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("DELETE FROM runs")
    data = admin_client.get("/api/admin/overview", headers=bearer("admin-token")).json()
    assert data["pipeline"] == {"runs": [], "latest_errors": {}}
