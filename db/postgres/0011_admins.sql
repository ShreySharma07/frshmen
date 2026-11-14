-- Who may open /admin (docs/decisions.md, 2026-11-13). A table of its own rather than a column on
-- students: nothing a signed-in person can write touches it. Rows are added by hand in the
-- Supabase SQL editor:
--   INSERT INTO admins (user_id) SELECT id FROM auth.users WHERE email = '<your sign-in email>';
CREATE TABLE admins (
  user_id  uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  added_at timestamptz NOT NULL DEFAULT now()
);

-- RLS on with no policies, and no grants: the browser's roles can't read or write it at all.
-- The API reads it with the database owner's connection (Hyperdrive).
ALTER TABLE admins ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON admins FROM anon, authenticated;
