# Architecture decisions

Newest first. Each entry: date, options considered, choice, why.

---

## 2026-10-05 — LLM for ambiguous (`maybe`) cases
- **Options:** rules-only at first · Gemini free tier · Groq free tier
- **Choice:** Rules-only for now.
- **Why:** Matches build order (LLM fallback is step 5). Measure how many jobs land in `maybe` before adding a provider and its rate limits. Revisit at step 5.

## 2026-10-05 — Storage
- **Options:** JSON/SQLite committed to a `data` branch · Cloudflare D1 · Supabase free tier
- **Choice:** Cloudflare D1.
- **Why:** A real SQL database with a free tier, no inactivity pausing (unlike Supabase), and no repo bloat from committed data.
- **Free-tier limits (checked 2026-10-05):** 500 MB per DB, 5 GB per account, 10 DBs, **5M rows read/day, 100k rows written/day** (resets 00:00 UTC; queries error once hit), 7-day Time Travel.
- **Consequence:** The pipeline must write only new or changed rows (compare `content_hash`), never re-upsert every posting each run. Indexed writes count extra rows.

## 2026-10-05 — Scheduler
- **Options:** GitHub Actions cron · Cloudflare Workers cron
- **Choice:** GitHub Actions cron.
- **Why:** Free, runs Python natively, no per-run CPU cap for long fetch jobs.
- **Limits:** Cron can start 5–30 min late; scheduled workflows auto-disable after 60 days without repo activity; private repos get 2,000 min/month. The Cloudflare API token lives in GitHub Actions secrets.

## 2026-10-05 — Pipeline language
- **Options:** Python · TypeScript
- **Choice:** Python.
- **Why:** Strongest text/regex/testing ecosystem for YoE extraction; runs natively on GitHub Actions.
