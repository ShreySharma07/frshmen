-- The profile dashboard (docs/decisions.md, 2026-11-04): a tracker of saved and applied jobs,
-- and the Gemini fit checks, at most 5 a day. tests/test_rls.py runs as Supabase's roles to
-- prove nobody reaches another person's rows.

-- --- Tracker: applications start as "saved" --------------------------------------------------

ALTER TABLE applications DROP CONSTRAINT applications_status_check;
ALTER TABLE applications
  ADD CONSTRAINT applications_status_check
    CHECK (status IN ('saved', 'applied', 'interview', 'offer', 'rejected')),
  ALTER COLUMN status SET DEFAULT 'saved',
  -- applied_at now means what it says: set when the status first becomes "applied".
  ALTER COLUMN applied_at DROP NOT NULL,
  ALTER COLUMN applied_at DROP DEFAULT,
  ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();

CREATE FUNCTION applications_stamp() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status <> 'saved' AND NEW.applied_at IS NULL THEN NEW.applied_at := now(); END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER applications_stamp BEFORE INSERT OR UPDATE ON applications
  FOR EACH ROW EXECUTE FUNCTION applications_stamp();

-- A person adds a job (theirs only), moves it along, or removes it. Nothing else is writable.
REVOKE ALL ON applications FROM anon, authenticated;
GRANT SELECT, DELETE ON applications TO authenticated;
GRANT INSERT (student_id, job_id, status) ON applications TO authenticated;
GRANT UPDATE (status) ON applications TO authenticated;

DROP POLICY "own applications" ON applications;
CREATE POLICY "read own applications" ON applications FOR SELECT TO authenticated
  USING (student_id = (SELECT auth.uid()));
CREATE POLICY "add own applications" ON applications FOR INSERT TO authenticated
  WITH CHECK (student_id = (SELECT auth.uid()));
CREATE POLICY "move own applications" ON applications FOR UPDATE TO authenticated
  USING (student_id = (SELECT auth.uid())) WITH CHECK (student_id = (SELECT auth.uid()));
CREATE POLICY "remove own applications" ON applications FOR DELETE TO authenticated
  USING (student_id = (SELECT auth.uid()));

-- --- Fit checks ------------------------------------------------------------------------------
-- Written only by the API (as the database owner), after it has verified who is asking and
-- counted their checks. People can read their own verdicts and nothing else.

CREATE TABLE fit_checks (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  student_id uuid NOT NULL REFERENCES students (id) ON DELETE CASCADE,
  job_id     text NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
  result     jsonb NOT NULL,  -- fit, score, matched, missing, experience, advice (api/src/fit.py)
  model      text,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- "How many checks in the last 24 hours" and "the latest verdicts" read by person, newest first.
CREATE INDEX fit_checks_student_idx ON fit_checks (student_id, created_at DESC);

ALTER TABLE fit_checks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON fit_checks FROM anon, authenticated;
GRANT SELECT ON fit_checks TO authenticated;
CREATE POLICY "read own fit checks" ON fit_checks FOR SELECT TO authenticated
  USING (student_id = (SELECT auth.uid()));
