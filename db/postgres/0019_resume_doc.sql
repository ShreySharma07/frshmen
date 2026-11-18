-- The resume's structure (docs/decisions.md, 2026-11-17): name, contact lines and sections of entries
-- (title, where, dates, bullets), read in the browser from the uploaded PDF's text positions and
-- fonts, then edited as fields. Templates lay it out; resume_text is written from it in the same
-- save, so the agent and fit checks read the same words. The person writes their own, like 0004.

ALTER TABLE students
  ADD COLUMN resume_doc jsonb CHECK (resume_doc IS NULL OR (jsonb_typeof(resume_doc) = 'object'
                                     AND pg_column_size(resume_doc) <= 131072));

GRANT INSERT (resume_doc) ON students TO authenticated;
GRANT UPDATE (resume_doc) ON students TO authenticated;
