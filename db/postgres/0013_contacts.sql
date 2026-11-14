-- The contact lists Shrey uploads in /admin (docs/decisions.md, 2026-11-13, C1/C2): HR and
-- recruiting contacts, and YC founders. Personal data under India's DPDP Act, so it gets the
-- narrowest use: only the API reads it (no grants to the Data API), the agent reveals one email at
-- a time inside a draft, phone numbers are never shown to users, every reveal is logged, and a
-- row is deleted on request.
CREATE TABLE contacts (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind        text NOT NULL CHECK (kind IN ('hr', 'founder')),
  name        text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
  company     text NOT NULL CHECK (char_length(btrim(company)) BETWEEN 1 AND 120),
  title       text CHECK (char_length(title) <= 160),
  email       text CHECK (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' AND char_length(email) <= 254),
  phone       text CHECK (char_length(phone) <= 40),  -- admin-only, never sent to a user
  linkedin    text CHECK (linkedin ~ '^https?://' AND char_length(linkedin) <= 300),
  location    text CHECK (char_length(location) <= 120),
  yc_batch    text CHECK (char_length(yc_batch) <= 12),       -- founders: e.g. "W24"
  company_url text CHECK (company_url ~ '^https?://' AND char_length(company_url) <= 300),
  notes       text CHECK (char_length(notes) <= 1000),      -- e.g. "hires freshers", "AI infra"
  source      text NOT NULL CHECK (char_length(btrim(source)) BETWEEN 1 AND 200),  -- where the row came from
  added_at    timestamptz NOT NULL DEFAULT now()
);
-- One row per person: the same email can't be uploaded twice (case-insensitive).
CREATE UNIQUE INDEX contacts_email_idx ON contacts (lower(email)) WHERE email IS NOT NULL;
CREATE INDEX contacts_company_idx ON contacts (lower(company));

-- Each time a user is shown a contact's email (the agent's draft), for the daily cap and the log.
CREATE TABLE contact_reveals (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  student_id  uuid NOT NULL REFERENCES students (id) ON DELETE CASCADE,
  contact_id  bigint REFERENCES contacts (id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX contact_reveals_student_idx ON contact_reveals (student_id, created_at);

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE contact_reveals ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON contacts, contact_reveals FROM anon, authenticated;
