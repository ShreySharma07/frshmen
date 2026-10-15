-- Multi-user schema for Supabase Postgres (M2, docs/plan.md §12).
-- Kept apart from db/migrations/, which wrangler applies to D1.
--
-- Things that exist on their own (universities, students, companies, jobs) get an id.
-- Things that happen between them (a student applying to a job) get their own table.
-- Labels from our rules live apart from the posting, so a re-label never touches the job row.

-- --- Things ---------------------------------------------------------------------------------

CREATE TABLE universities (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name       text NOT NULL UNIQUE,  -- one correct spelling; students pick from the list
  created_at timestamptz NOT NULL DEFAULT now()
);

-- A student is a Supabase Auth user, so the id is the auth user's id, not a new number.
CREATE TABLE students (
  id            uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  name          text NOT NULL,
  university_id bigint REFERENCES universities (id),
  yoe           numeric(3, 1) NOT NULL DEFAULT 0 CHECK (yoe >= 0),  -- "fresher" is derived from this
  resume_path   text,  -- a path in Supabase Storage, never the file itself
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE companies (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name         text NOT NULL UNIQUE,  -- the upsert key when the pipeline meets a company
  careers_site text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- The posting as the company wrote it. Changes rarely; written by the pipeline.
CREATE TABLE jobs (
  id               text PRIMARY KEY,  -- "<source>:<board>:<external_id>", stable, so re-runs upsert
  company_id       bigint NOT NULL REFERENCES companies (id),
  source           text NOT NULL,     -- greenhouse | lever | ashby | careersite | oracle ...
  title            text NOT NULL,
  url              text NOT NULL,
  location_raw     text,
  department       text,
  employment_type  text,
  posted_at        timestamptz,       -- only if the source gives it
  first_seen_at    timestamptz NOT NULL,  -- set once, never overwritten
  status           text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  missed_runs      smallint NOT NULL DEFAULT 0,  -- closed after 2 runs absent from a working board
  description_text text,              -- dropped for long-closed jobs to stay inside 500 MB
  content_hash     text NOT NULL      -- unchanged hash => the pipeline skips the write
);

-- The job list: open jobs, newest first. Ends in the sort key so a page reads ~20 rows.
CREATE INDEX jobs_recent_idx ON jobs (status, (COALESCE(posted_at, first_seen_at)) DESC, id DESC);
CREATE INDEX jobs_company_idx ON jobs (company_id);

-- --- Things that happen between them ---------------------------------------------------------

CREATE TABLE applications (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  student_id uuid NOT NULL REFERENCES students (id) ON DELETE CASCADE,
  job_id     text NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
  status     text NOT NULL DEFAULT 'applied'
             CHECK (status IN ('applied', 'interview', 'offer', 'rejected')),
  applied_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (student_id, job_id)  -- applying twice is refused by the database
);

-- "How many students applied to this job" counts by job.
CREATE INDEX applications_job_idx ON applications (job_id);

-- What our rules concluded about a job. A new row only when the result changes (label_hash),
-- keeping the current and previous label per job so a rules update can be checked for
-- fresher-precision regressions.
CREATE TABLE job_labels (
  job_id           text NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
  rules_version    integer NOT NULL,
  labelled_at      timestamptz NOT NULL DEFAULT now(),
  label_hash       text NOT NULL,     -- fingerprint of the values below
  level            text NOT NULL CHECK (level IN ('fresher', 'maybe', 'experienced')),
  level_confidence real,
  level_reason     text,
  yoe_min          real,
  yoe_max          real,
  yoe_evidence     text,
  batch_years      smallint[],
  role_match       boolean NOT NULL DEFAULT false,
  role_family      text,              -- ai_ml | backend | mobile | generic_swe
  location_type    text CHECK (location_type IN ('remote', 'hybrid', 'onsite')),
  countries        text[],
  cities           text[],
  eligible         boolean NOT NULL DEFAULT true,
  visa_sponsorship text NOT NULL DEFAULT 'unknown' CHECK (visa_sponsorship IN ('yes', 'no', 'unknown')),
  skills           text[],
  evidence         jsonb,             -- every snippet behind level, role and location
  PRIMARY KEY (job_id, rules_version)
);

-- The label the site shows: each job's newest row.
CREATE VIEW current_labels AS
SELECT DISTINCT ON (job_id) *
FROM job_labels
ORDER BY job_id, rules_version DESC;

-- --- Pipeline bookkeeping (carried over from D1) ---------------------------------------------

CREATE TABLE runs (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  finished_at      timestamptz NOT NULL,
  companies_ok     integer NOT NULL,
  companies_failed integer NOT NULL,
  jobs_seen        integer NOT NULL,
  jobs_new         integer NOT NULL,
  jobs_changed     integer NOT NULL,
  jobs_closed      integer NOT NULL,
  errors           jsonb              -- company -> error
);

-- Filter lists and counts, computed once per pipeline run instead of on every page load.
CREATE TABLE meta (
  key        text PRIMARY KEY,
  value      jsonb NOT NULL,
  updated_at timestamptz NOT NULL
);

-- --- Row-level security ----------------------------------------------------------------------
-- Supabase also serves every table over its public Data API. With RLS on, nothing is readable
-- there unless a policy below allows it. The FastAPI Worker and the pipeline connect as the
-- database owner, which RLS does not restrict.

ALTER TABLE universities ENABLE ROW LEVEL SECURITY;
ALTER TABLE students     ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies    ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs         ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_labels   ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs         ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta         ENABLE ROW LEVEL SECURITY;

-- Public facts: anyone can read, only the pipeline (owner) writes.
CREATE POLICY "read universities" ON universities FOR SELECT USING (true);
CREATE POLICY "read companies"    ON companies    FOR SELECT USING (true);
CREATE POLICY "read jobs"         ON jobs         FOR SELECT USING (true);
CREATE POLICY "read job labels"   ON job_labels   FOR SELECT USING (true);

-- A student sees and edits only their own row and their own applications.
CREATE POLICY "own profile" ON students
  FOR ALL USING (id = auth.uid()) WITH CHECK (id = auth.uid());
CREATE POLICY "own applications" ON applications
  FOR ALL USING (student_id = auth.uid()) WITH CHECK (student_id = auth.uid());

-- The view runs with the caller's permissions, so job_labels' policy applies through it.
ALTER VIEW current_labels SET (security_invoker = true);
