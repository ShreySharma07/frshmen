-- Reposted jobs merge into the original (docs/decisions.md, 2026-10-16).
-- When a company re-lists a role under a new ATS id, the original jobs row stays (with its
-- applications, labels and first_seen_at) and takes the new listing's date, URL and text.
-- The new listing's id is recorded here, so later runs update the original instead of
-- adding a second card.

CREATE TABLE job_aliases (
  alias_id   text PRIMARY KEY,  -- the reposted listing's "<source>:<board>:<external_id>"
  job_id     text NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (alias_id <> job_id)
);

CREATE INDEX job_aliases_job_idx ON job_aliases (job_id);

-- Fingerprint of company + normalised title + location, set by the pipeline. Jobs sharing it
-- are repost candidates; the pipeline then compares descriptions before merging, so two
-- separate "SDE 1, Bengaluru" batches with different text stay two jobs.
ALTER TABLE jobs ADD COLUMN repost_key text;
CREATE INDEX jobs_repost_key_idx ON jobs (repost_key) WHERE repost_key IS NOT NULL;

-- Pipeline bookkeeping, not public: RLS on with no policy keeps it off the Data API.
ALTER TABLE job_aliases ENABLE ROW LEVEL SECURITY;
