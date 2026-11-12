"""Job text in Supabase Storage: the key shared by pipeline and API, the pipeline's store
against a stand-in for Storage's REST API, the API's read with its fallback, and (with
PG_TEST_URL) the publish, backfill and measuring paths."""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

import backfill_job_text as backfill
import job_text
import measure_storage
import publish_pg as pub
import text_store
from test_publish_pg import job

BASE = "https://proj.supabase.co"


class FakeStorage:
    """The three requests TextStore makes, over a dict keyed by object name."""

    def __init__(self, fail_on: str | None = None):
        self.objects: dict[str, bytes] = {}
        self.fail_on = fail_on
        self.seen: list[tuple[str, dict[str, str]]] = []

    def __call__(self, method, url, headers, body):
        self.seen.append((method, headers))
        name = url.split(f"/object/{job_text.BUCKET}", 1)[1].lstrip("/")
        if method == "POST":
            if name == self.fail_on:
                return 500, b"storage is down"
            self.objects[name] = body
            return 200, b"{}"
        if method == "GET":
            return (200, self.objects[name]) if name in self.objects else (400, b'{"error":"not_found"}')
        for n in json.loads(body)["prefixes"]:
            self.objects.pop(n, None)
        return 200, b"[]"


def store_on(fake):
    return text_store.TextStore(BASE, "secret", send=fake)


def test_key_is_stable_url_safe_and_distinct():
    k = job_text.key("careersite:acme:https://acme.com/jobs/1?x=y")
    assert k == job_text.key("careersite:acme:https://acme.com/jobs/1?x=y")
    assert k.endswith(".txt") and len(k) == 64 + 4 and k[:64].isalnum()
    assert k != job_text.key("careersite:acme:https://acme.com/jobs/2?x=y")
    assert job_text.public_url(BASE + "/", "a:1") == f"{BASE}/storage/v1/object/public/job-text/{job_text.key('a:1')}"


def test_store_round_trip_skips_empty_text_upserts_and_deletes():
    fake = FakeStorage()
    store = store_on(fake)
    assert store.put_many([("a:1", "Über 3 years"), ("a:2", ""), ("a:3", "x")]) == 2
    assert store.get("a:1") == "Über 3 years" and store.get("a:2") is None
    method, headers = fake.seen[0]
    assert method == "POST" and headers["x-upsert"] == "true" and headers["Authorization"] == "Bearer secret"
    assert store.delete_many(["a:1", "missing"]) == 2 and store.get("a:1") is None


def test_a_failed_upload_raises_instead_of_passing_silently():
    with pytest.raises(RuntimeError, match="a:1"):
        store_on(FakeStorage(fail_on=job_text.key("a:1"))).put_many([("a:1", "x")])


def test_from_env_is_off_when_unset_and_stops_when_half_set():
    assert text_store.from_env({}) is None
    with pytest.raises(SystemExit, match="SUPABASE_SECRET_KEY"):
        text_store.from_env({"SUPABASE_URL": BASE})
    assert text_store.from_env({"SUPABASE_URL": BASE, "SUPABASE_SECRET_KEY": "k"}).objects == f"{BASE}/storage/v1/object/job-text"


def reads(texts, broken=False):
    """What the API is given to read job text: an async function from job id to text or None."""
    async def read(job_id):
        if broken:
            raise RuntimeError("storage is down")
        return texts.get(job_id)
    return read


def test_api_read_returns_text_and_none_when_missing_off_or_failing(capsys):
    assert asyncio.run(job_text.read(reads({"a:1": "stored"}), "a:1")) == "stored"
    assert asyncio.run(job_text.read(reads({}), "a:2")) is None
    assert asyncio.run(job_text.read(None, "a:1")) is None
    assert asyncio.run(job_text.read(reads({}, broken=True), "a:1")) is None
    assert "a:1" in capsys.readouterr().out  # the failure is logged, not hidden


def test_api_reads_only_when_switched_on():
    class Req:
        def __init__(self, **env):
            self.app = type("App", (), {"state": type("State", (), {})()})()
            self.scope = {"env": type("Env", (), env)()}
    assert job_text.reader(Req(SUPABASE_URL=BASE)) is None  # bucket not filled yet: no wasted lookups
    assert job_text.reader(Req(SUPABASE_URL=BASE, JOB_TEXT="off")) is None
    assert job_text.reader(Req(JOB_TEXT="on")) is None
    assert callable(job_text.reader(Req(SUPABASE_URL=BASE, JOB_TEXT="on")))


# --- Against Postgres (PG_TEST_URL; CI runs a Postgres service) ------------------------------

PG = os.environ.get("PG_TEST_URL")
needs_pg = pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")
T0 = datetime(2026, 11, 11, tzinfo=timezone.utc)


@pytest.fixture
def pg():
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA public; "
                     "CREATE SCHEMA auth; CREATE TABLE auth.users (id uuid PRIMARY KEY); "
                     "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS 'SELECT NULL::uuid'")
        for f in sorted(Path("db/postgres").glob("*.sql")):
            conn.execute(f.read_text())
        yield conn


def payload(*jobs):
    return {"jobs": list(jobs), "boards_ok": [{"source": "ashby", "company_slug": "acme"}], "errors": {}}


@needs_pg
def test_publish_writes_text_to_storage_for_new_and_changed_jobs_only(pg):
    store = store_on(FakeStorage())
    first = pub.publish(pg, payload(job("1"), job("2")), now=T0, store=store)
    assert first["texts"] == 2 and store.get("ashby:acme:1") == job("1")["description_text"]

    again = pub.publish(pg, payload(job("1"), job("2")), now=T0, store=store)
    assert again["texts"] == 0  # unchanged jobs cost no uploads

    changed = job("2", desc="a rewritten posting " * 40)
    assert pub.publish(pg, payload(job("1"), changed), now=T0, store=store)["texts"] == 1
    assert store.get("ashby:acme:2") == changed["description_text"]
    # The jobs table still holds the text during the switch-over.
    assert pg.execute("SELECT description_text FROM jobs WHERE id = 'ashby:acme:2'").fetchone()[0] == changed["description_text"]


@needs_pg
def test_failed_upload_rolls_the_whole_run_back(pg):
    store = store_on(FakeStorage(fail_on=job_text.key("ashby:acme:2")))
    with pytest.raises(RuntimeError):
        pub.publish(pg, payload(job("1"), job("2")), now=T0, store=store)
    assert pg.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0  # nothing committed, so the next run retries


@needs_pg
def test_backfill_copies_everything_and_verify_spots_a_difference(pg):
    pub.publish(pg, payload(job("1"), job("2"), job("3", desc="")), now=T0)  # stored before the bucket existed
    fake = FakeStorage()
    store = store_on(fake)
    assert backfill.copy_all(pg, None, log=lambda _: None)[0] == 2 and not fake.objects  # dry run
    jobs, size = backfill.copy_all(pg, store, log=lambda _: None)
    assert jobs == 2 and size > 0 and backfill.verify(pg, store, 10) == []
    store.put("ashby:acme:1", "tampered")
    assert backfill.verify(pg, store, 10) == ["ashby:acme:1"]


@needs_pg
def test_measure_report_counts_jobs_and_text(pg):
    pub.publish(pg, payload(job("1"), job("2")), now=T0)
    text = measure_storage.report(pg)
    assert "Jobs stored: **2** (2 open, 0 closed), 2 with text" in text
    assert "| ashby | 2 | 2 |" in text and "bytes** a job" in text
