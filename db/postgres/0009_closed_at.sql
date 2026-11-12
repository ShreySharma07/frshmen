-- When a job closed, so closed jobs can be deleted 14 days later (docs/decisions.md, 2026-11-11
-- and 2026-11-12: two fifths of stored jobs were closed, and rows are what fills the free tier).
ALTER TABLE jobs ADD COLUMN closed_at timestamptz;

-- Jobs already closed carry no date. They count as closed now: the full 14 days of grace, so a
-- board that comes back within it reopens its jobs instead of listing them as new.
UPDATE jobs SET closed_at = now() WHERE status = 'closed';

-- The purge reads closed jobs by date; open jobs (most rows) stay out of the index.
CREATE INDEX jobs_closed_at_idx ON jobs (closed_at) WHERE status = 'closed';
