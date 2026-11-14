-- The agent chat's daily allowance (docs/decisions.md, 2026-11-13, A1): one row per message a
-- person sends, counted over the last 24 hours like fit checks. The conversation itself isn't
-- stored: the browser keeps it and sends the recent turns with each message.
CREATE TABLE agent_messages (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  student_id  uuid NOT NULL REFERENCES students (id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX agent_messages_student_idx ON agent_messages (student_id, created_at);

ALTER TABLE agent_messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON agent_messages FROM anon, authenticated;
