"""Row-level security for profiles and resumes (db/postgres/0004_profiles.sql).

The browser talks to Supabase directly (docs/decisions.md, 2026-10-30), so these policies are
the only guard on a person's resume. Every test runs as one of Supabase's request roles, anon or
authenticated, with the JWT claims PostgREST would set, on top of Supabase's default grants
(tests/supabase_stub.py). Shrey's condition for that design: these tests are non-negotiable.
A failure here is a security bug, never a test to loosen.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg import errors

import supabase_stub

PG = os.environ.get("PG_TEST_URL")
pytestmark = pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")

ALICE = uuid.UUID("00000000-0000-4000-8000-00000000a11c")
BOB = uuid.UUID("00000000-0000-4000-8000-000000000b0b")
# Tables the pipeline owns. Nobody on the Data API may change them.
# Each with a plain column to try an UPDATE on.
PIPELINE_TABLES = {"universities": "name", "companies": "name", "jobs": "title", "job_labels": "level",
                   "runs": "finished_at", "meta": "value", "job_aliases": "job_id"}
DENIED = (errors.InsufficientPrivilege,)  # RLS refusals and missing grants both raise this


@pytest.fixture(scope="module", autouse=True)
def database():
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute(supabase_stub.DROP)
        supabase_stub.install(conn)
        for f in sorted(Path("db/postgres").glob("*.sql")):
            conn.execute(f.read_text())
        conn.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (ALICE, BOB))
    yield


@pytest.fixture(autouse=True)
def clean():
    """Each test starts with Bob's profile and resume in place and nothing of Alice's."""
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("DELETE FROM students; DELETE FROM storage.objects")
        conn.execute("INSERT INTO students (id, name, resume_path, resume_text) VALUES (%s, 'Bob', %s, 'Bob secret resume')",
                     (BOB, f"{BOB}/resume.pdf"))
        conn.execute("INSERT INTO storage.objects (bucket_id, name, owner) VALUES ('resumes', %s, %s)",
                     (f"{BOB}/resume.pdf", BOB))
    yield


@contextmanager
def as_role(role: str, uid: uuid.UUID | None = None):
    """A connection that behaves like one PostgREST request: SET ROLE plus the JWT claims."""
    with psycopg.connect(PG) as conn:
        claims = {"role": role, **({"sub": str(uid)} if uid else {})}
        conn.execute("SELECT set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
        conn.execute(f"SET LOCAL ROLE {role}")
        yield conn
        conn.rollback()


def as_alice():
    return as_role("authenticated", ALICE)


def denied(role_ctx, sql: str, params=()):
    """True when the statement is refused outright (no grant, or an RLS check failed)."""
    with role_ctx as conn:
        try:
            conn.execute(sql, params)
        except DENIED:
            return True
    return False


def rowcount(role_ctx, sql: str, params=()) -> int:
    with role_ctx as conn:
        return conn.execute(sql, params).rowcount


def rows(role_ctx, sql: str, params=()) -> list:
    with role_ctx as conn:
        return conn.execute(sql, params).fetchall()


# --- Whole-database guarantees ---------------------------------------------------------------

def test_every_public_table_has_rls_on():
    # A new table without RLS would be fully readable and writable through Supabase's Data API.
    with psycopg.connect(PG) as conn:
        off = conn.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                           "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity").fetchall()
    assert off == []


def test_every_public_view_runs_as_the_caller():
    # A view runs as its owner unless security_invoker is set, which would skip RLS entirely.
    with psycopg.connect(PG) as conn:
        views = conn.execute("SELECT c.relname, c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                             "WHERE n.nspname = 'public' AND c.relkind IN ('v', 'm')").fetchall()
    assert views, "expected job_cards and current_labels"
    assert all("security_invoker=true" in (opts or []) for _, opts in views), views


def test_no_public_function_bypasses_rls():
    # SECURITY DEFINER functions run as their owner, and public functions are callable over RPC.
    with psycopg.connect(PG) as conn:
        definers = conn.execute("SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                                "WHERE n.nspname = 'public' AND p.prosecdef").fetchall()
    assert definers == []


# --- Profiles ---------------------------------------------------------------------------------

def test_anon_cannot_see_or_create_profiles():
    assert denied(as_role("anon"), "SELECT * FROM students")
    assert denied(as_role("anon"), "INSERT INTO students (id, name) VALUES (%s, 'x')", (ALICE,))
    assert denied(as_role("anon"), "UPDATE students SET name = 'x'")
    assert denied(as_role("anon"), "DELETE FROM students")


def test_signed_in_user_sees_only_their_own_profile():
    assert rows(as_alice(), "SELECT id FROM students") == []  # Bob's row is invisible
    with as_alice() as conn:
        conn.execute("INSERT INTO students (id, name, yoe, grad_year, target_roles) VALUES (%s, 'Alice', 0, 2026, '{ai_ml}')", (ALICE,))
        assert [r[0] for r in conn.execute("SELECT id FROM students").fetchall()] == [ALICE]
        conn.commit()
    assert rows(as_alice(), "SELECT name, grad_year, target_roles FROM students") == [("Alice", 2026, ["ai_ml"])]


def test_cannot_create_a_profile_for_someone_else():
    assert denied(as_alice(), "INSERT INTO students (id, name) VALUES (%s, 'Mallory')", (BOB,))
    assert denied(as_alice(), "INSERT INTO students (id, name) VALUES (%s, 'Ghost')", (uuid.uuid4(),))


def test_cannot_read_change_or_delete_someone_elses_profile():
    assert rows(as_alice(), "SELECT resume_text FROM students WHERE id = %s", (BOB,)) == []
    assert rowcount(as_alice(), "UPDATE students SET name = 'pwned' WHERE id = %s", (BOB,)) == 0
    assert rowcount(as_alice(), "DELETE FROM students WHERE id = %s", (BOB,)) == 0
    assert denied(as_alice(), "TRUNCATE students")
    with psycopg.connect(PG) as conn:  # as the owner: Bob's row is untouched
        assert conn.execute("SELECT name, resume_text FROM students WHERE id = %s", (BOB,)).fetchone() == ("Bob", "Bob secret resume")


def test_cannot_take_over_a_profile_by_changing_ids_or_server_columns():
    with as_alice() as conn:
        conn.execute("INSERT INTO students (id, name) VALUES (%s, 'Alice')", (ALICE,))
        conn.commit()
    assert denied(as_alice(), "UPDATE students SET id = %s WHERE id = %s", (BOB, ALICE))
    assert denied(as_alice(), "UPDATE students SET created_at = now() - interval '9 years'")
    assert denied(as_alice(), "UPDATE students SET updated_at = now()")


def test_cannot_point_a_profile_at_someone_elses_resume():
    bob_file = f"{BOB}/resume.pdf"
    assert denied(as_alice(), "INSERT INTO students (id, name, resume_path) VALUES (%s, 'Alice', %s)", (ALICE, bob_file))
    with as_alice() as conn:
        conn.execute("INSERT INTO students (id, name, resume_path) VALUES (%s, 'Alice', %s)", (ALICE, f"{ALICE}/resume.pdf"))
        conn.commit()
    assert denied(as_alice(), "UPDATE students SET resume_path = %s", (bob_file,))
    assert denied(as_alice(), "UPDATE students SET resume_path = %s", (f"{ALICE}/../{BOB}/resume.pdf",))


def test_profile_values_are_checked():
    for sql, params in [
        ("INSERT INTO students (id, name, target_roles) VALUES (%s, 'A', '{admin}')", (ALICE,)),
        ("INSERT INTO students (id, name) VALUES (%s, '   ')", (ALICE,)),
        ("INSERT INTO students (id, name, yoe) VALUES (%s, 'A', -1)", (ALICE,)),
        ("INSERT INTO students (id, name, resume_text) VALUES (%s, 'A', repeat('x', 60001))", (ALICE,)),
    ]:
        with as_alice() as conn, pytest.raises(errors.CheckViolation):
            conn.execute(sql, params)


def test_updated_at_moves_on_every_save():
    with as_alice() as conn:
        conn.execute("INSERT INTO students (id, name) VALUES (%s, 'Alice')", (ALICE,))
        conn.commit()
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("UPDATE students SET updated_at = now() - interval '1 day' WHERE id = %s", (ALICE,))
    with as_alice() as conn:
        conn.execute("UPDATE students SET yoe = 1")
        assert conn.execute("SELECT updated_at > now() - interval '1 minute' FROM students").fetchone() == (True,)


# --- Resume files -----------------------------------------------------------------------------

def upload(role_ctx, name: str, bucket: str = "resumes"):
    return denied(role_ctx, "INSERT INTO storage.objects (bucket_id, name, owner) VALUES (%s, %s, %s)", (bucket, name, ALICE))


def test_resume_bucket_is_private_pdf_only_and_small():
    with psycopg.connect(PG) as conn:
        assert conn.execute("SELECT public, file_size_limit, allowed_mime_types FROM storage.buckets WHERE id = 'resumes'"
                            ).fetchone() == (False, 5 * 1024 * 1024, ["application/pdf"])


def test_anon_cannot_list_read_or_upload_resumes():
    assert rows(as_role("anon"), "SELECT name FROM storage.objects") == []
    assert upload(as_role("anon"), f"{ALICE}/resume.pdf")


def test_user_can_upload_and_replace_only_their_own_resume():
    with as_alice() as conn:
        conn.execute("INSERT INTO storage.objects (bucket_id, name, owner) VALUES ('resumes', %s, %s)", (f"{ALICE}/resume.pdf", ALICE))
        assert conn.execute("UPDATE storage.objects SET metadata = '{}' WHERE name = %s", (f"{ALICE}/resume.pdf",)).rowcount == 1
        conn.commit()
    assert rows(as_alice(), "SELECT name FROM storage.objects") == [(f"{ALICE}/resume.pdf",)]


def test_cannot_upload_outside_your_one_resume_path():
    assert upload(as_alice(), f"{BOB}/resume.pdf")
    assert upload(as_alice(), f"{ALICE}/other.pdf")
    assert upload(as_alice(), f"{ALICE}/resume.pdf/../../{BOB}/resume.pdf")
    assert upload(as_alice(), "resume.pdf")
    assert upload(as_alice(), f"{ALICE}/resume.pdf", bucket="avatars")


def test_cannot_read_replace_move_or_delete_someone_elses_resume():
    bob_file = f"{BOB}/resume.pdf"
    assert rows(as_alice(), "SELECT name FROM storage.objects") == []
    assert rowcount(as_alice(), "UPDATE storage.objects SET owner = %s WHERE name = %s", (ALICE, bob_file)) == 0
    assert rowcount(as_alice(), "DELETE FROM storage.objects WHERE name = %s", (bob_file,)) == 0
    with as_alice() as conn:
        conn.execute("INSERT INTO storage.objects (bucket_id, name, owner) VALUES ('resumes', %s, %s)", (f"{ALICE}/resume.pdf", ALICE))
        conn.commit()
    # Moving your own file to any other path fails the update's check.
    for target in (bob_file, f"{ALICE}/copy.pdf", f"{uuid.uuid4()}/resume.pdf"):
        assert denied(as_alice(), "UPDATE storage.objects SET name = %s WHERE name = %s", (target, f"{ALICE}/resume.pdf"))
    with psycopg.connect(PG) as conn:
        assert conn.execute("SELECT owner FROM storage.objects WHERE name = %s", (bob_file,)).fetchone() == (BOB,)


# --- The pipeline's tables --------------------------------------------------------------------

@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize("table", PIPELINE_TABLES)
def test_data_api_cannot_change_pipeline_tables(role, table):
    uid = ALICE if role == "authenticated" else None
    col = PIPELINE_TABLES[table]
    assert denied(as_role(role, uid), f"DELETE FROM {table}")
    assert denied(as_role(role, uid), f"UPDATE {table} SET {col} = {col}")
    assert denied(as_role(role, uid), f"TRUNCATE {table}")


@pytest.mark.parametrize("table", ["runs", "meta", "job_aliases"])
def test_pipeline_bookkeeping_is_not_readable(table):
    assert denied(as_role("anon"), f"SELECT * FROM {table}")


def test_public_job_data_stays_readable():
    assert rows(as_role("anon"), "SELECT count(*) FROM job_cards") == [(0,)]
