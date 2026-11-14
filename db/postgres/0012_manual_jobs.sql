-- Jobs an admin adds by hand in /admin (docs/decisions.md, 2026-11-13, D1): a posting seen on a
-- careers page we can't read, a referral, a college notice. The pipeline reads the open rows as
-- the "manual" source (sources/manual.py), so they are labelled by the same rules as every job;
-- closing a row closes the job on the next run.
CREATE TABLE manual_jobs (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  company          text NOT NULL CHECK (char_length(btrim(company)) BETWEEN 1 AND 120),
  title            text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
  url              text NOT NULL CHECK (url ~ '^https?://' AND char_length(url) <= 2000),
  location_raw     text NOT NULL DEFAULT '' CHECK (char_length(location_raw) <= 200),
  description_text text NOT NULL CHECK (char_length(btrim(description_text)) BETWEEN 1 AND 60000),
  posted_at        timestamptz,
  added_by         uuid REFERENCES auth.users (id) ON DELETE SET NULL,
  added_at         timestamptz NOT NULL DEFAULT now(),
  closed_at        timestamptz
);

-- Only the API (as an admin) and the pipeline write here; the Data API sees nothing.
ALTER TABLE manual_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON manual_jobs FROM anon, authenticated;
