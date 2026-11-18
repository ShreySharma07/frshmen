-- Daily limits counted per person, not per profile row (docs/decisions.md, 2026-11-18, security H1).
--
-- Before: each use was a row referencing students(id) ON DELETE CASCADE, and a person may delete and
-- re-create their own profile through the Data API (0004), which wiped their counters. Deleting the
-- account and signing up again with the same email did the same. Now every use is recorded under
-- `who`: a keyed hash of the person's normalised email (api/src/usage.py), with no link to the
-- profile or the login, so neither deleting nor signing up again resets it. A limit only looks back
-- 24 hours, so rows are kept for 48 and then deleted by the API itself.
-- Only the API reads or writes it (no grants), like contacts.
CREATE TABLE usage_events (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  who         text NOT NULL CHECK (who ~ '^[0-9a-f]{64}$'),
  kind        text NOT NULL CHECK (kind IN ('agent_message', 'fit_check', 'tailor', 'contact_reveal')),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX usage_events_who_idx ON usage_events (who, kind, created_at);
CREATE INDEX usage_events_created_idx ON usage_events (created_at);
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON usage_events FROM anon, authenticated;

-- agent_messages only counted messages; usage_events does that now.
DROP TABLE agent_messages;

-- The email-reveal log is an audit trail for the people whose addresses were shown (Shrey,
-- 2026-11-18): it outlives the account that saw them, with the account's id removed.
ALTER TABLE contact_reveals ALTER COLUMN student_id DROP NOT NULL;
ALTER TABLE contact_reveals DROP CONSTRAINT contact_reveals_student_id_fkey;
ALTER TABLE contact_reveals ADD CONSTRAINT contact_reveals_student_id_fkey
  FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE SET NULL;
