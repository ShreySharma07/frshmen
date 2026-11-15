-- A person's own LinkedIn connections (docs/decisions.md, 2026-11-15): uploaded from LinkedIn's
-- Connections.csv export, read by the agent's "who do I know at X". LinkedIn has no connections
-- API for apps like ours, and automating LinkedIn is ruled out (CLAUDE.md), so the person's own
-- export is the only source.
--
-- The browser parses the file and writes the rows through Supabase's Data API as the signed-in
-- person, so RLS below is the guard: each person reads, adds and deletes only their own rows.
-- Email addresses in the export are dropped in the browser and have no column here: a connection
-- is someone to message on LinkedIn, not an address list.
CREATE TABLE connections (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  student_id   uuid NOT NULL DEFAULT auth.uid() REFERENCES students (id) ON DELETE CASCADE,
  name         text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
  company      text CHECK (char_length(company) <= 120),
  position     text CHECK (char_length(position) <= 160),
  linkedin     text CHECK (linkedin ~ '^https://([a-z]+\.)?linkedin\.com/' AND char_length(linkedin) <= 300),
  connected_on date,
  added_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX connections_student_company_idx ON connections (student_id, lower(company));

-- Free tier: 500 MB in all. LinkedIn caps connections at 30,000; most students have far fewer.
-- 5,000 rows is ~1 MB per person, and the upload keeps the most recent if there are more.
-- Checked once per insert statement (a whole file is one statement), not once per row.
CREATE FUNCTION connections_cap() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM connections c WHERE c.student_id IN (SELECT DISTINCT student_id FROM added)
             GROUP BY c.student_id HAVING COUNT(*) > 5000) THEN
    RAISE EXCEPTION 'at most 5000 connections per person' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER connections_cap AFTER INSERT ON connections REFERENCING NEW TABLE AS added
  FOR EACH STATEMENT EXECUTE FUNCTION connections_cap();

ALTER TABLE connections ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON connections FROM anon, authenticated;
-- Rows are replaced as a whole (delete all, insert the new file), never edited.
GRANT SELECT, DELETE ON connections TO authenticated;
GRANT INSERT (name, company, position, linkedin, connected_on) ON connections TO authenticated;
CREATE POLICY "read own connections" ON connections FOR SELECT TO authenticated
  USING (student_id = (SELECT auth.uid()));
CREATE POLICY "add own connections" ON connections FOR INSERT TO authenticated
  WITH CHECK (student_id = (SELECT auth.uid()));
CREATE POLICY "delete own connections" ON connections FOR DELETE TO authenticated
  USING (student_id = (SELECT auth.uid()));
