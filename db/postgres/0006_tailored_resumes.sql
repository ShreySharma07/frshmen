-- Part B.3 (docs/decisions.md, 2026-11-04): a resume reworded toward one job by Gemini, at most
-- 2 per person in any 24 hours. Like fit_checks: written only by the API, which counts them and
-- runs the no-new-claims check; people read their own and nothing else.

CREATE TABLE tailored_resumes (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  student_id uuid NOT NULL REFERENCES students (id) ON DELETE CASCADE,
  job_id     text NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
  result     jsonb NOT NULL,  -- sections of lines, each with its source lines (api/src/tailor.py)
  model      text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tailored_resumes_student_idx ON tailored_resumes (student_id, created_at DESC);

ALTER TABLE tailored_resumes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON tailored_resumes FROM anon, authenticated;
GRANT SELECT ON tailored_resumes TO authenticated;
CREATE POLICY "read own tailored resumes" ON tailored_resumes FOR SELECT TO authenticated
  USING (student_id = (SELECT auth.uid()));
