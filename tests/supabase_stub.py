"""The parts of a Supabase database that our migrations rely on but don't create.

Kept close to the real thing on purpose, because tests/test_rls.py trusts it: the anon and
authenticated roles, Supabase's default grants on public (everything, to both roles), auth.uid()
reading the request's JWT claims the way PostgREST sets them, and storage.buckets / storage.objects
with RLS on.
"""

from __future__ import annotations

import psycopg

ROLES = ("anon", "authenticated")

SQL = """
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);
-- Supabase's definition: the JWT's sub, as PostgREST exposes it.
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT coalesce(nullif(current_setting('request.jwt.claim.sub', true), ''),
                  (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'))::uuid
$$;

CREATE SCHEMA storage;
CREATE TABLE storage.buckets (
  id                 text PRIMARY KEY,
  name               text NOT NULL UNIQUE,
  owner              uuid,
  public             boolean DEFAULT false,
  file_size_limit    bigint,
  allowed_mime_types text[],
  created_at         timestamptz DEFAULT now(),
  updated_at         timestamptz DEFAULT now()
);
CREATE TABLE storage.objects (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bucket_id  text REFERENCES storage.buckets (id),
  name       text,
  owner      uuid,
  owner_id   text,
  metadata   jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (bucket_id, name)
);
-- Supabase's helper: the folders of an object path, without the file name.
CREATE FUNCTION storage.foldername(name text) RETURNS text[] LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE _parts text[];
BEGIN
  SELECT string_to_array(name, '/') INTO _parts;
  RETURN _parts[1:array_length(_parts, 1) - 1];
END $$;
ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA public, auth, storage TO anon, authenticated;
GRANT EXECUTE ON FUNCTION auth.uid(), storage.foldername(text) TO anon, authenticated;
GRANT ALL ON storage.buckets, storage.objects TO anon, authenticated;
-- Supabase's defaults: every table, sequence and function later created in public is fully
-- granted to both roles, so only RLS and our own REVOKEs hold anything back.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon, authenticated;
"""


def install(conn: psycopg.Connection) -> None:
    """Run on a database whose public, auth and storage schemas were just dropped."""
    for role in ROLES:
        # Roles are cluster-wide and outlive the schemas, so create them once.
        conn.execute(f"DO $$ BEGIN CREATE ROLE {role} NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    conn.execute(SQL)


DROP = "DROP SCHEMA IF EXISTS public CASCADE; DROP SCHEMA IF EXISTS auth CASCADE; DROP SCHEMA IF EXISTS storage CASCADE; CREATE SCHEMA public"
