-- The dashboard's weekly applications goal (docs/decisions.md, 2026-11-04), default 5. People
-- set their own, so it joins the columns they may write (0004 lists them one by one).

ALTER TABLE students
  ADD COLUMN weekly_goal smallint NOT NULL DEFAULT 5 CHECK (weekly_goal BETWEEN 1 AND 50);

GRANT INSERT (weekly_goal) ON students TO authenticated;
GRANT UPDATE (weekly_goal) ON students TO authenticated;
