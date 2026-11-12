# Setting up the job-text store (Supabase Storage)

Job descriptions move out of the `jobs` table into a Supabase Storage bucket, so the free 500 MB
database can hold many more jobs (`docs/decisions.md`, 2026-11-12). Cloudflare R2 was the first
choice but needs a payment card that Cloudflare would not accept; Supabase Storage needs none
and the project already uses it for resumes.

Free tier (checked 2026-11-12): 1 GB of files. At about 2.3 KB a description that is roughly
400,000 jobs. The code is merged but **off** until these steps are done; until then everything
reads and writes the `jobs` table as before.

## Steps, in order

1. **The bucket creates itself.** Merging adds `db/postgres/0008_job_text_bucket.sql`, and the
   "Supabase migrations" workflow creates the public `job-text` bucket. Check it under Supabase
   → Storage.
2. **Copy the project's secret key.** Supabase → Project Settings → API Keys → the secret key
   (`sb_secret_...`; on older projects, `service_role`). This key can write anywhere in the
   project, so it goes only into GitHub's secrets, never into the site or the repo.
3. **Add it to GitHub.** Repo → Settings → Secrets and variables → Actions → New repository
   secret → `SUPABASE_SECRET_KEY`. From the next pipeline run, new and changed jobs are written
   to Storage as well as the table; the publish step prints "job text: also written to Storage".
4. **Copy the existing descriptions.** Actions → "Copy job text to Storage" → run with the dry
   run ticked, read the size, then run again with it unticked. It finishes with
   "verify passed: 300 random jobs match". About 40,000 jobs take 20 to 40 minutes.
5. **Let the API read from Storage.** Repo → Settings → Secrets and variables → Actions →
   Variables → New repository variable → `JOB_TEXT` = `on`. Then Actions → "Deploy site" → Run
   workflow. Open a job on the site: the description should look the same.

## Not done yet (the next change, after step 5 has run for a few days)

- Stop writing the text to the `jobs` table and drop the column. Before that: pay moves to its
  own column (the list reads it from the first line of the text today), and repost matching
  stores a small fingerprint instead of comparing full texts.
- Delete a job's text from Storage 14 days after it closes.

## Undo

Set `JOB_TEXT` to `off` and redeploy, and remove the `SUPABASE_SECRET_KEY` secret. The `jobs`
table still holds every description, so nothing is lost.
