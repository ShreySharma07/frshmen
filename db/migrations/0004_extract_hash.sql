-- Fingerprint of a job's extracted values: a rule change rewrites only rows whose results changed.
ALTER TABLE jobs ADD COLUMN extract_hash TEXT;
