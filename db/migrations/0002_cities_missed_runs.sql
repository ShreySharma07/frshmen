-- cities: Indian cities found in location_raw (JSON array), for the page's City filter.
-- missed_runs: consecutive runs a job was absent from a board that fetched OK; closed at 2.
ALTER TABLE jobs ADD COLUMN cities TEXT;
ALTER TABLE jobs ADD COLUMN missed_runs INTEGER NOT NULL DEFAULT 0;
