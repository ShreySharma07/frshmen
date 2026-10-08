-- The page now lists every open job, newest first (docs/decisions.md, 2026-10-08).
-- Both list indexes end in the page's sort key, so a page of 20 reads ~20 rows instead of
-- the whole table. idx_jobs_feed led with role_match, which the default view no longer filters on.
DROP INDEX IF EXISTS idx_jobs_feed;
CREATE INDEX IF NOT EXISTS idx_jobs_recent ON jobs (status, COALESCE(posted_at, first_seen_at) DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_level ON jobs (status, level, COALESCE(posted_at, first_seen_at) DESC, id DESC);

-- Filter lists (companies, countries, counts) computed once per pipeline run instead of on
-- every page load: over ~21k jobs those GROUP BYs would read ~100k rows per visit.
CREATE TABLE IF NOT EXISTS meta (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,  -- JSON
  updated_at TEXT NOT NULL
);
