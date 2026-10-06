# frshmen

A personal job board that shows only fresher-level AI/ML and Python backend roles, each with the
sentence from the posting that decided its label. See `CLAUDE.md` for goals and rules and
`docs/decisions.md` for why things are built this way.

## How it fits together

```
company boards (Greenhouse / Lever / Ashby)
   └─ scripts/fetch_jobs.py      fetch → normalize → dedupe → classify (extract/) → data/jobs.json
        └─ scripts/publish_d1.py writes only new/changed/closed jobs to Cloudflare D1
             └─ api/  (FastAPI on a Python Worker)  /api/jobs, /api/jobs/{id}, /api/meta
                  └─ web/ (React)  served by the same Worker as static assets
```

## Run it locally

```sh
pip install -r requirements-dev.txt uvicorn
python scripts/fetch_jobs.py                       # needs network access to the job boards
python scripts/publish_d1.py --sqlite data/local.db
(cd web && npm ci && npm run build)
python scripts/dev_api.py                          # http://127.0.0.1:8000
```

For live-reloading UI work, run `python scripts/dev_api.py` and `npm run dev` in `web/` (it proxies `/api`).

## Checks

```sh
pytest                                  # all tests
python scripts/eval_extractor.py        # fresher precision on labeled real postings (must stay 100%)
(cd web && npm run typecheck)
```

## Deploy (GitHub Actions)

Repo secrets needed: `CLOUDFLARE_API_TOKEN` (Workers + D1 edit) and `CLOUDFLARE_ACCOUNT_ID`.

- **Deploy site** runs on pushes to `main` that touch `api/`, `web/` or migrations: builds the page,
  applies D1 migrations, deploys the Worker.
- **Fetch and publish jobs** (Actions tab → Run workflow) fetches every verified board and publishes changes to D1.
- **Verify company boards** checks `config/companies.yaml` against the ATS APIs on PRs that edit it.
