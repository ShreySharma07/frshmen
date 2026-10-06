-- Core schema from CLAUDE.md, plus role and evidence fields.
-- D1 free tier: 100k rows written/day, and every index adds a written row per write,
-- so indexes are limited to what the page's queries actually filter on.

CREATE TABLE IF NOT EXISTS jobs (
  id               TEXT PRIMARY KEY,          -- "<source>:<company_slug>:<external_id>"
  source           TEXT NOT NULL,             -- greenhouse | lever | ashby
  company          TEXT NOT NULL,
  company_slug     TEXT NOT NULL,
  title            TEXT NOT NULL,
  url              TEXT NOT NULL,
  location_raw     TEXT,
  location_type    TEXT,                      -- remote | hybrid | onsite (ATS hint until extract/ owns it)
  countries        TEXT,                      -- JSON array
  department       TEXT,
  employment_type  TEXT,
  posted_at        TEXT,                      -- ISO UTC, only if the source gives it
  first_seen_at    TEXT NOT NULL,             -- set once, never overwritten; drives the "new" view
  status           TEXT NOT NULL DEFAULT 'open',  -- open | closed (missing from a later fetch)
  description_text TEXT,
  content_hash     TEXT NOT NULL,             -- change => re-extract
  extract_version  INTEGER NOT NULL,          -- bump in publish_d1.py to re-classify everything once
  yoe_min          REAL,
  yoe_max          REAL,
  yoe_evidence     TEXT,
  batch_years      TEXT,                      -- JSON array
  level            TEXT NOT NULL,             -- fresher | maybe | experienced
  level_confidence REAL,
  level_reason     TEXT,
  role_match       INTEGER NOT NULL DEFAULT 0,
  role_family      TEXT,                      -- ai_ml | backend | generic_swe
  role_reason      TEXT,
  visa_sponsorship TEXT NOT NULL DEFAULT 'unknown',  -- yes | no | unknown (extractor not built yet)
  skills           TEXT,                      -- JSON array (match scoring, later)
  match_score      REAL,
  evidence         TEXT                       -- JSON: every snippet behind level and role
);

-- The page's main query: open target-role jobs of a level, newest first.
CREATE INDEX IF NOT EXISTS idx_jobs_feed ON jobs (status, role_match, level, first_seen_at DESC);

CREATE TABLE IF NOT EXISTS runs (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  finished_at       TEXT NOT NULL,
  companies_ok      INTEGER NOT NULL,
  companies_failed  INTEGER NOT NULL,
  jobs_seen         INTEGER NOT NULL,
  jobs_new          INTEGER NOT NULL,
  jobs_changed      INTEGER NOT NULL,
  jobs_closed       INTEGER NOT NULL,
  errors            TEXT                      -- JSON object: company -> error
);
