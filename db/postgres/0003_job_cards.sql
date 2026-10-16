-- What the API reads (M3 switch-over): one row per job with its company name and current label.

-- The page shows why a job matched the target roles; D1 had this, job_labels didn't yet.
ALTER TABLE job_labels ADD COLUMN role_reason text;

-- Marks each job's newest label row, kept by the pipeline. Finding "newest" per query instead
-- (DISTINCT ON, or a per-job lookup) cost ~3 s for a 27k-job count; a flag lets Postgres join
-- the current rows in one pass.
ALTER TABLE job_labels ADD COLUMN is_current boolean NOT NULL DEFAULT false;
UPDATE job_labels l SET is_current = true
FROM (SELECT job_id, MAX(rules_version) AS v FROM job_labels GROUP BY job_id) m
WHERE l.job_id = m.job_id AND l.rules_version = m.v;
CREATE UNIQUE INDEX job_labels_current_idx ON job_labels (job_id) WHERE is_current;

CREATE VIEW job_cards WITH (security_invoker = true) AS
SELECT
  j.id, j.source, c.name AS company, j.title, j.url, j.location_raw, j.department, j.employment_type,
  j.posted_at, j.first_seen_at, j.status, j.description_text,
  l.rules_version, l.level, l.level_confidence, l.level_reason, l.yoe_min, l.yoe_max, l.yoe_evidence,
  l.batch_years, l.role_match, l.role_family, l.role_reason, l.location_type, l.countries, l.cities,
  l.eligible, l.visa_sponsorship, l.skills, l.evidence
FROM jobs j
JOIN companies c ON c.id = j.company_id
LEFT JOIN job_labels l ON l.job_id = j.id AND l.is_current;
