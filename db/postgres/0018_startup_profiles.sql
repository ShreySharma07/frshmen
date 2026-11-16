-- What each startup on the YC founders list builds (docs/decisions.md, 2026-11-16), so the agent can
-- suggest startups that fit a person whether or not they have an opening on Aventra.
--
-- Filled by scripts/refresh_startups.py from, in order: the uploaded CSV's description column
-- (contacts.description), the yc-oss dataset, and the startup's own homepage meta description.
-- Only the API reads it, like contacts.

-- A founders CSV may carry a one-liner or description of the startup.
ALTER TABLE contacts ADD COLUMN description text CHECK (char_length(description) <= 1000);

CREATE TABLE startup_profiles (
  key            text PRIMARY KEY CHECK (key = lower(btrim(key)) AND char_length(key) BETWEEN 1 AND 120),  -- lower(contacts.company)
  name           text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
  website        text CHECK (website ~ '^https?://' AND char_length(website) <= 300),
  one_liner      text CHECK (char_length(one_liner) <= 300),
  description    text CHECK (char_length(description) <= 1000),
  tags           text[] NOT NULL DEFAULT '{}',
  status         text CHECK (char_length(status) <= 40),          -- yc-oss: Active, Inactive, Acquired, Public
  source         text CHECK (source IN ('csv', 'yc-oss', 'homepage')),  -- where the description came from; NULL = none found
  categories     text[] NOT NULL DEFAULT '{}',                    -- config/role_families.yaml keys
  skills         text[] NOT NULL DEFAULT '{}',                    -- config/skills.yaml names
  homepage_tried_at timestamptz,                                  -- last homepage read, so it is tried once per 30 days
  homepage_etag  text CHECK (char_length(homepage_etag) <= 200),
  homepage_modified text CHECK (char_length(homepage_modified) <= 100),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE startup_profiles ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON startup_profiles FROM anon, authenticated;
