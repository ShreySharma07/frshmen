-- Every job's general category (docs/decisions.md, 2026-11-13): AI/ML, backend, frontend, data,
-- DevOps, QA, ... from extract/category.py, so people whose roles aren't the profile's target
-- roles can filter by theirs. role_family keeps its meaning (which target role matched).
ALTER TABLE job_labels ADD COLUMN category text;

-- Rebuilt with the new column at the end (CREATE OR REPLACE VIEW may only append columns).
CREATE OR REPLACE VIEW job_cards WITH (security_invoker = true) AS
SELECT
  j.id, j.source, c.name AS company, j.title, j.url, j.location_raw, j.department, j.employment_type,
  j.posted_at, j.first_seen_at, j.status, j.description_text,
  l.rules_version, l.level, l.level_confidence, l.level_reason, l.yoe_min, l.yoe_max, l.yoe_evidence,
  l.batch_years, l.role_match, l.role_family, l.role_reason, l.location_type, l.countries, l.cities,
  l.eligible, l.visa_sponsorship, l.skills, l.evidence, l.category
FROM jobs j
JOIN companies c ON c.id = j.company_id
LEFT JOIN job_labels l ON l.job_id = j.id AND l.is_current;
