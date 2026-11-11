# Setting up Cloudflare R2 for job text

Job descriptions move out of Postgres into an R2 bucket so the free 500 MB database can hold
many more jobs (`docs/decisions.md`, 2026-11-11 storage). The code is merged but **off** until
these steps are done; until then everything reads and writes Postgres as before.

Free tier (checked 2026-11-11): 10 GB stored, 1 million writes and 10 million reads a month, no
charge for downloads. Cloudflare asks for a card to turn R2 on, and bills only above those
limits; the pipeline writes a few hundred objects a run.

## Steps, in order

1. **Measure first.** GitHub → Actions → "Measure storage" → Run workflow. Paste the summary into
   `docs/strategy/worldwide-coverage.md` under "Where we are".
2. **Create the bucket.** Cloudflare dashboard → R2 → Create bucket → name `aventra-job-text`,
   location Automatic. Leave public access off.
3. **Create an access key for the pipeline.** R2 → Manage API tokens → Create Account API token
   → permission "Object Read & Write", limited to the `aventra-job-text` bucket. Copy the
   Access Key ID and the Secret Access Key (shown once).
4. **Add them to GitHub.** Repo → Settings → Secrets and variables → Actions → New repository
   secret: `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`. The account id is read from the
   existing `CLOUDFLARE_ACCOUNT_ID`. From the next pipeline run, new and changed jobs are
   written to R2 as well as Postgres; the publish step prints "job text: also written to R2".
5. **Copy the existing descriptions.** Actions → "Copy job text to R2" → run with the dry run
   ticked, read the size, then run again with it unticked. It finishes with
   "verify passed: 300 random jobs match".
6. **Let the API read from R2.** In `api/wrangler.jsonc`, uncomment the `r2_buckets` block and
   merge; the deploy binds the bucket. The Cloudflare API token used by the deploy needs
   "Workers R2 Storage: Edit" if it doesn't have it already. Open a job on the site: the
   description should look the same, and Workers Logs should show no "job_text" lines.

## Not done yet (the next change, after step 6 has run for a few days)

- Stop writing the text to Postgres and drop the column. Before that: pay moves to its own
  column (the list reads it from the first line of the text today), and repost matching stores
  a small fingerprint instead of comparing full texts.
- Delete a job's text from R2 14 days after it closes.

## Undo

Remove the two GitHub secrets and comment the binding out again. Postgres still holds every
description, so nothing is lost.
