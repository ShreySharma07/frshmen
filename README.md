# frshmen

A personal job board that shows only fresher-level AI/ML and Python backend roles, each with the
sentence from the posting that decided its label. See `CLAUDE.md` for goals and rules and
`docs/decisions.md` for why things are built this way.

## How it fits together

```
company boards (Greenhouse / Lever / Ashby)
   └─ scripts/fetch_jobs.py      fetch → normalize → dedupe → classify (extract/) → data/jobs.json
        └─ scripts/publish_pg.py writes only new/changed/closed jobs to Supabase Postgres
             └─ api/  (FastAPI on a Python Worker, via Hyperdrive)  /api/jobs, /api/jobs/{id}, /api/meta
                  └─ site/ (Next.js static export)  served by the same Worker as static assets
```

## Run it locally

```sh
pip install -r requirements-dev.txt uvicorn
export SUPABASE_DB_URL=postgresql://...           # a local or Supabase Postgres
scripts/apply_pg_migrations.sh                     # creates the tables (db/postgres/)
python scripts/fetch_jobs.py                       # needs network access to the job boards
python scripts/publish_pg.py
(cd site && npm ci && npm run build)
python scripts/dev_api.py                          # http://127.0.0.1:8000, the site + /api like the Worker
```

For live-reloading UI work, run `python scripts/dev_api.py` and `npm run dev` in `site/` (it forwards `/api`).

## Checks

```sh
PG_TEST_URL=postgresql://... pytest      # all tests; API and publisher tests need a throwaway Postgres
python scripts/eval_extractor.py        # fresher precision on labeled real postings (must stay 100%)
(cd site && npm run lint && npx tsc --noEmit && npm run check:tokens)
```

## Deploy (GitHub Actions)

Repo secrets needed: `CLOUDFLARE_API_TOKEN` (Workers edit), `CLOUDFLARE_ACCOUNT_ID` and `SUPABASE_DB_URL`
(Supabase Session pooler connection string).

- **Deploy site** runs on pushes to `main` that touch `api/` or `site/`: builds the site and deploys the Worker.
- **Supabase migrations** applies new `db/postgres/*.sql` files on pushes to `main` that touch them.
- **Fetch and publish jobs** (every 3 hours, or Actions tab → Run workflow) fetches every verified board and
  publishes changes to Supabase.
- **Verify company boards** checks `config/companies.yaml` against the ATS APIs on PRs that edit it.
