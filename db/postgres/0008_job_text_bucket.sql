-- Job descriptions move out of the jobs table into Supabase Storage (docs/decisions.md,
-- 2026-11-12), so the free 500 MB database holds the facts lists and filters need and the free
-- 1 GB of Storage holds the long text.
--
-- A public bucket: a description is the company's own public posting, and a public URL lets the
-- API read one with a plain request and no key. Plain text only, 200 KB an object (stored
-- descriptions are capped far below that). Only the pipeline writes, with the project's secret
-- key, which RLS does not restrict; with no policies here, signed-in people and visitors can
-- neither list nor write.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('job-text', 'job-text', true, 204800, ARRAY['text/plain'])
ON CONFLICT (id) DO UPDATE SET public = true, file_size_limit = EXCLUDED.file_size_limit,
                               allowed_mime_types = EXCLUDED.allowed_mime_types;
