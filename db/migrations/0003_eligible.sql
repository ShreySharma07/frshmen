-- eligible: 1 when the location fits the profile (India except onsite-only Bengaluru/Hyderabad,
-- remote with no country, or abroad with visa sponsorship/relocation). The reason is in evidence.
ALTER TABLE jobs ADD COLUMN eligible INTEGER NOT NULL DEFAULT 1;
