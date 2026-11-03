-- Part B.1: a signed-in person's profile and resume (docs/decisions.md, 2026-10-30).
-- The browser reads and writes these through Supabase's Data API and Storage directly, so the
-- policies and grants below are the only thing between one person's resume and everyone else.
-- tests/test_rls.py runs as Supabase's anon and authenticated roles to prove they hold.

-- --- Profile fields --------------------------------------------------------------------------

ALTER TABLE students
  ADD COLUMN grad_year    smallint CHECK (grad_year BETWEEN 1990 AND 2040),
  -- The job list's Role filter families (site/src/lib/api.ts); empty = no preference.
  ADD COLUMN target_roles text[] NOT NULL DEFAULT '{}'
             CHECK (target_roles <@ ARRAY['ai_ml', 'backend', 'mobile']),
  ADD COLUMN resume_name  text CHECK (char_length(resume_name) <= 200),     -- the uploaded file's name
  ADD COLUMN resume_text  text CHECK (char_length(resume_text) <= 60000),  -- pulled out in the browser
  ADD COLUMN updated_at   timestamptz NOT NULL DEFAULT now(),
  ADD CONSTRAINT students_name_length CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
  ADD CONSTRAINT students_yoe_max CHECK (yoe <= 50);

-- One resume per person, always at the same path, so the policies can name it exactly.
CREATE FUNCTION resume_path_for(uid uuid) RETURNS text LANGUAGE sql IMMUTABLE AS
  $$ SELECT uid::text || '/resume.pdf' $$;

CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS
  $$ BEGIN NEW.updated_at := now(); RETURN NEW; END $$;
CREATE TRIGGER students_updated_at BEFORE UPDATE ON students
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- --- Who may touch a profile -----------------------------------------------------------------
-- Supabase grants anon and authenticated everything on public tables by default; RLS narrows
-- rows, grants narrow the operations. Both are set here so neither alone is load-bearing.
-- TRUNCATE ignores RLS, so it is never granted.

REVOKE ALL ON students FROM anon, authenticated;
GRANT SELECT, DELETE ON students TO authenticated;
-- id comes from the signed-in user and never changes; created_at and updated_at are the server's.
GRANT INSERT (id, name, university_id, yoe, grad_year, target_roles, resume_path, resume_name, resume_text)
  ON students TO authenticated;
GRANT UPDATE (name, university_id, yoe, grad_year, target_roles, resume_path, resume_name, resume_text)
  ON students TO authenticated;

-- The old catch-all policy (0001) is split so each operation states its own rule.
DROP POLICY "own profile" ON students;
CREATE POLICY "read own profile" ON students FOR SELECT TO authenticated
  USING (id = (SELECT auth.uid()));
CREATE POLICY "create own profile" ON students FOR INSERT TO authenticated
  WITH CHECK (id = (SELECT auth.uid())
              AND (resume_path IS NULL OR resume_path = resume_path_for((SELECT auth.uid()))));
CREATE POLICY "edit own profile" ON students FOR UPDATE TO authenticated
  USING (id = (SELECT auth.uid()))
  WITH CHECK (id = (SELECT auth.uid())
              AND (resume_path IS NULL OR resume_path = resume_path_for((SELECT auth.uid()))));
CREATE POLICY "delete own profile" ON students FOR DELETE TO authenticated
  USING (id = (SELECT auth.uid()));

-- Applications are not used yet; keep anon out and TRUNCATE away from both roles.
REVOKE ALL ON applications FROM anon;
REVOKE TRUNCATE, TRIGGER, REFERENCES ON applications FROM authenticated;

-- The pipeline's tables are read-only to the Data API. RLS already refuses writes (no policy);
-- the grants say the same, and TRUNCATE, which RLS does not cover, goes.
REVOKE ALL ON universities, companies, jobs, job_labels, runs, meta, job_aliases FROM anon, authenticated;
GRANT SELECT ON universities, companies, jobs, job_labels, job_cards, current_labels TO anon, authenticated;

-- --- Resume files ----------------------------------------------------------------------------
-- A private bucket: no public URLs, PDF only, 5 MB (Storage enforces type and size on upload).
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('resumes', 'resumes', false, 5242880, ARRAY['application/pdf'])
ON CONFLICT (id) DO UPDATE SET public = false, file_size_limit = EXCLUDED.file_size_limit,
                               allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Each person reaches exactly one object: <their id>/resume.pdf. Replacing it (upsert) needs
-- select, insert and update.
CREATE POLICY "read own resume" ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'resumes' AND name = resume_path_for((SELECT auth.uid())));
CREATE POLICY "upload own resume" ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'resumes' AND name = resume_path_for((SELECT auth.uid())));
CREATE POLICY "replace own resume" ON storage.objects FOR UPDATE TO authenticated
  USING (bucket_id = 'resumes' AND name = resume_path_for((SELECT auth.uid())))
  WITH CHECK (bucket_id = 'resumes' AND name = resume_path_for((SELECT auth.uid())));
CREATE POLICY "delete own resume" ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'resumes' AND name = resume_path_for((SELECT auth.uid())));
