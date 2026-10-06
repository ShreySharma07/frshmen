# Architecture decisions

Newest first. Each entry: date, options considered, choice, why.

---

## 2026-10-06 — Serve React from the API Worker (Workers Static Assets) instead of Cloudflare Pages
- **Options:** one Python Worker serving FastAPI + the React build · React on Pages + separate API Worker
- **Choice:** One Worker. Supersedes the "Cloudflare Pages" part of the frontend decision below.
- **Why:** One deploy and one URL, no CORS. Static asset requests are free and don't count toward Workers' 100k requests/day; only `/api/*` calls run Python. Cloudflare now recommends Static Assets over Pages for new projects.

## 2026-10-06 — Count plain "Software Engineer" titles when the work is Python + AI (pending Shrey's confirmation)
- **Options:** only AI/ML and backend titles · also plain SWE titles whose description shows Python and AI/ML work
- **Choice (proposed by Claude, toggle in `config/profile.yaml` → `generic_swe.enabled`):** include them.
- **Why:** New-grad postings at AI companies are often titled just "Software Engineer - New Grad" (e.g. Scale AI) while asking for Python, LLMs and evals. Without this they'd never show. Cost: more generic SWE roles at AI companies, since "AI" appears in most of their boilerplate.

## 2026-10-06 — Add junior Python backend roles to targets
- **Options:** AI/ML roles only · AI/ML + Python backend
- **Choice:** AI/ML + junior Python backend (Python stack only: FastAPI/Django/Flask).
- **Why:** Python backend is a strong adjacent fit for Shrey's skills (Python, FastAPI) and widens the fresher pool. Frontend, mobile, QA and sales stay excluded.
- **Where:** `config/profile.yaml` → `target_roles`, `backend_requires_any`.

## 2026-10-06 — Probe Workable only when guessed
- **Options:** probe every ATS for every company · skip Workable unless it is the guessed ATS
- **Choice:** Workable only when guessed.
- **Why:** Workable throttles hard (429 with `Retry-After: 0`) and only 3 of ~260 companies use it; probing it for everyone slowed runs several-fold. Cost: a company that silently moved to Workable needs its `ats` set by hand.

## 2026-10-05 — Company discovery
- **Options:** hand-curated ~50 seed list · seed list + auto-discovery from YC/funding lists
- **Choice:** Curated list of ~200 companies, including YC AI startups. Claude drafts it, Shrey prunes.
- **Why:** Bigger coverage than 50 while keeping every entry verified as AI/ML with a working public ATS board (Greenhouse/Lever/Ashby). YC companies are added via their own ATS boards, not by scraping login-walled YC pages.

## 2026-10-05 — Backend API
- **Options:** Cloudflare Python Workers · Render free web service · no backend (static `jobs.json`)
- **Choice:** FastAPI on Cloudflare Python Workers, reading D1 via a native binding.
- **Why:** Shrey wants a Python backend; this keeps API, DB and frontend on one platform with no sleep/cold-start penalty (Render sleeps after 15 min idle, ~1 min wake).
- **Free-tier limits:** 100k requests/day, short CPU time per request. Tooling is `pywrangler` (newer, thinner docs). Every API read counts toward D1's 5M rows read/day, so list queries must use indexes and pagination.
- **Consequence:** Pipeline step 6 now writes to D1; the page calls the API instead of reading a static JSON.

## 2026-10-05 — Frontend and hosting
- **Options:** plain HTML/JS · small framework · React; GitHub Pages · Cloudflare Pages
- **Choice:** React (Vite + TypeScript) on Cloudflare Pages. Claude builds it; Shrey reviews.
- **Why:** A polished UI is the goal. Cloudflare Pages keeps hosting on the same platform as D1 and the API. Repo is public.

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
