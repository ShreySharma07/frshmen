"""Job text in R2: the key shared by pipeline and API, the pipeline's store against a stand-in
S3 client, the API's read-through with its fallback, and (with PG_TEST_URL) the publish,
backfill and measuring paths."""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

import backfill_r2
import job_text
import measure_storage
import publish_pg as pub
import text_store
from test_publish_pg import job


class FakeS3:
    """The three calls TextStore makes, over a dict."""

    class exceptions:  # noqa: N801 - mirrors boto3's client.exceptions
        class NoSuchKey(Exception):
            pass

    def __init__(self, fail_on: str | None = None):
        self.objects: dict[str, bytes] = {}
        self.fail_on = fail_on

    def put_object(self, Bucket, Key, Body, ContentType):  # noqa: N803
        if self.fail_on == Key:
            raise RuntimeError("R2 is down")
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        if Key not in self.objects:
            raise self.exceptions.NoSuchKey()
        body = self.objects[Key]
        return {"Body": type("Body", (), {"read": lambda self: body})()}

    def delete_objects(self, Bucket, Delete):  # noqa: N803
        for o in Delete["Objects"]:
            self.objects.pop(o["Key"], None)


def test_key_is_stable_safe_and_distinct():
    k = job_text.key("careersite:acme:https://acme.com/jobs/1?x=y")
    assert k == job_text.key("careersite:acme:https://acme.com/jobs/1?x=y")
    assert k.startswith("text/") and len(k) == 5 + 64 and k[5:].isalnum()
    assert k != job_text.key("careersite:acme:https://acme.com/jobs/2?x=y")


def test_store_round_trip_skips_empty_text_and_deletes():
    s3 = FakeS3()
    store = text_store.TextStore(s3, "b")
    assert store.put_many([("a:1", "Über 3 years"), ("a:2", ""), ("a:3", "x")]) == 2
    assert store.get("a:1") == "Über 3 years" and store.get("a:2") is None
    assert store.delete_many(["a:1", "missing"]) == 2 and store.get("a:1") is None


def test_from_env_is_off_when_unset_and_stops_when_half_set():
    assert text_store.from_env({}) is None
    with pytest.raises(SystemExit, match="R2_SECRET_ACCESS_KEY"):
        text_store.from_env({"R2_ACCOUNT_ID": "a", "R2_ACCESS_KEY_ID": "k", "R2_BUCKET": "b"})


class FakeBucket:
    """The Worker's R2 binding: get() resolves to an object with text(), or None."""

    def __init__(self, objects, broken=False):
        self.objects, self.broken = objects, broken

    async def get(self, key):
        if self.broken:
            raise RuntimeError("R2 is down")
        text = self.objects.get(key)
        if text is None:
            return None

        async def read():
            return text
        return type("Obj", (), {"text": staticmethod(read)})()


def test_api_read_returns_text_and_none_on_miss_no_bucket_or_failure(capsys):
    bucket = FakeBucket({job_text.key("a:1"): "stored"})
    assert asyncio.run(job_text.read(bucket, "a:1")) == "stored"
    assert asyncio.run(job_text.read(bucket, "a:2")) is None
    assert asyncio.run(job_text.read(None, "a:1")) is None
    assert asyncio.run(job_text.read(FakeBucket({}, broken=True), "a:1")) is None
    assert "a:1" in capsys.readouterr().out  # the failure is logged, not hidden


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
def test_publish_writes_text_to_r2_for_new_and_changed_jobs_only(pg):
    s3 = FakeS3()
    store = text_store.TextStore(s3, "b")
    first = pub.publish(pg, payload(job("1"), job("2")), now=T0, store=store)
    assert first["texts"] == 2 and store.get("ashby:acme:1") == job("1")["description_text"]

    again = pub.publish(pg, payload(job("1"), job("2")), now=T0, store=store)
    assert again["texts"] == 0  # unchanged jobs cost no R2 writes

    changed = job("2", desc="a rewritten posting " * 40)
    assert pub.publish(pg, payload(job("1"), changed), now=T0, store=store)["texts"] == 1
    assert store.get("ashby:acme:2") == changed["description_text"]
    # Postgres still holds the text during the switch-over.
    assert pg.execute("SELECT description_text FROM jobs WHERE id = 'ashby:acme:2'").fetchone()[0] == changed["description_text"]


@needs_pg
def test_failed_upload_rolls_the_whole_run_back(pg):
    store = text_store.TextStore(FakeS3(fail_on=job_text.key("ashby:acme:2")), "b")
    with pytest.raises(RuntimeError):
        pub.publish(pg, payload(job("1"), job("2")), now=T0, store=store)
    assert pg.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0  # nothing committed, so the next run retries


@needs_pg
def test_backfill_copies_everything_and_verify_spots_a_difference(pg):
    pub.publish(pg, payload(job("1"), job("2"), job("3", desc="")), now=T0)  # stored before R2 existed
    s3 = FakeS3()
    store = text_store.TextStore(s3, "b")
    assert backfill_r2.copy_all(pg, None, log=lambda _: None)[0] == 2 and not s3.objects  # dry run
    jobs, size = backfill_r2.copy_all(pg, store, log=lambda _: None)
    assert jobs == 2 and size > 0 and backfill_r2.verify(pg, store, 10) == []
    store.put("ashby:acme:1", "tampered")
    assert backfill_r2.verify(pg, store, 10) == ["ashby:acme:1"]


@needs_pg
def test_measure_report_counts_jobs_and_text(pg):
    pub.publish(pg, payload(job("1"), job("2")), now=T0)
    text = measure_storage.report(pg)
    assert "Jobs stored: **2** (2 open, 0 closed), 2 with text" in text
    assert "| ashby | 2 | 2 |" in text and "bytes** a job" in text
