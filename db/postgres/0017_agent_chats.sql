-- Saved agent chats (docs/decisions.md, 2026-11-15, option 1): the person's own conversations,
-- listed when they open /agent and reopened from there, on any device.
--
-- The browser writes them through Supabase's Data API as the signed-in person, so RLS below is the
-- guard: each person reads, adds, edits and deletes only their own. Email addresses revealed on
-- draft cards are taken out in the browser before saving (site/src/lib/chats.ts), and the check
-- below refuses a chat that still holds one.
CREATE TABLE agent_chats (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id  uuid NOT NULL DEFAULT auth.uid() REFERENCES students (id) ON DELETE CASCADE,
  title       text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 120),
  turns       jsonb NOT NULL CHECK (jsonb_typeof(turns) = 'array' AND pg_column_size(turns) <= 262144
                                    AND NOT jsonb_path_exists(turns, '$[*].cards[*].to ? (@ != null)')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX agent_chats_student_idx ON agent_chats (student_id, updated_at DESC);
CREATE TRIGGER agent_chats_updated_at BEFORE UPDATE ON agent_chats
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Keep the last 30 chats per person, each for 15 days since it was last used (Shrey, 2026-11-15). Old ones go when a
-- new chat is saved; the list also hides any past 15 days (lib/chats.ts).
CREATE FUNCTION agent_chats_trim() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM agent_chats c
   WHERE c.student_id IN (SELECT DISTINCT student_id FROM added)
     AND (c.updated_at < now() - interval '15 days'
          OR c.id IN (SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY student_id ORDER BY updated_at DESC) AS n
                                       FROM agent_chats WHERE student_id = c.student_id) r WHERE r.n > 30));
  RETURN NULL;
END $$;
CREATE TRIGGER agent_chats_trim AFTER INSERT ON agent_chats REFERENCING NEW TABLE AS added
  FOR EACH STATEMENT EXECUTE FUNCTION agent_chats_trim();

ALTER TABLE agent_chats ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON agent_chats FROM anon, authenticated;
GRANT SELECT, DELETE ON agent_chats TO authenticated;
GRANT INSERT (id, title, turns) ON agent_chats TO authenticated;
GRANT UPDATE (title, turns) ON agent_chats TO authenticated;
CREATE POLICY "read own chats" ON agent_chats FOR SELECT TO authenticated
  USING (student_id = (SELECT auth.uid()));
CREATE POLICY "add own chats" ON agent_chats FOR INSERT TO authenticated
  WITH CHECK (student_id = (SELECT auth.uid()));
CREATE POLICY "edit own chats" ON agent_chats FOR UPDATE TO authenticated
  USING (student_id = (SELECT auth.uid())) WITH CHECK (student_id = (SELECT auth.uid()));
CREATE POLICY "delete own chats" ON agent_chats FOR DELETE TO authenticated
  USING (student_id = (SELECT auth.uid()));
