# CLAUDE.md — Personal AI/ML Fresher Job Board

## What this project is
A personal job board for one user (Shrey). It polls company hiring sources continuously, extracts structured data from each posting, and shows only **fresher-level AI/ML roles** on a web page, newest first. Accuracy of filtering is the whole point: if a posting says "2+ years" anywhere in the description, it must NOT show up as a fresher role.

Read `skills.md` before touching extraction, sources, or filtering. It holds the reusable procedures for this repo.

## Working agreement (important)
- **Shrey makes the architectural decisions. Claude builds.** For any non-trivial choice (storage, hosting, scheduler, LLM provider, schema change), present 2-3 options with one-line tradeoffs and a recommendation, then wait for his call. Do not silently pick.
- Log every decision in `docs/decisions.md` (date, options considered, choice, why). Create the file on first decision.
- Ask a short clarifying question before big changes. Keep answers to the point.
- When explaining a concept, give a short analogy first.
- Small, reviewable commits. One concern per commit. Never commit secrets.

## Hard constraints
- **Free tools only.** No paid APIs, servers, or plans. Stay inside free tiers and note the limits of any tier we use.
- **Be a good citizen when fetching.** Prefer official public APIs and feeds over HTML scraping. Respect robots.txt and ToS. Do NOT scrape LinkedIn, Indeed, or Glassdoor. Identify the bot with a User-Agent, cache with ETag/If-Modified-Since, and rate-limit per host.
- **Precision over recall for the fresher filter.** A missed job is acceptable; a 3-YoE job shown as entry-level is a bug.
- Every extracted field must keep its **evidence** (the exact snippet it was derived from) so wrong results can be debugged.

## User profile (drives filtering and ranking)
- B.Tech CS with AI specialisation, graduated 2026 → eligible for "2026 batch", "new grad", "graduate", "0-1 year" roles. Also treat 2025/2027 batch targeting as a soft match.
- Target: AI/ML Engineer, ML Research Engineer, Applied Scientist (junior), Data Scientist (junior), LLM/GenAI Engineer, MLOps (junior), AI Engineer, **Python Backend Engineer (junior; Python stack such as FastAPI/Django)**, Research Intern → only if full-time conversion is stated. Plain "Software Engineer" titles count only when the description shows Python and AI/ML work (`generic_swe` toggle). **Android and React Native developer roles** also count (`mobile` in `config/profile.yaml`); iOS-only and Flutter don't. Skip frontend/QA/sales roles. Role keywords live in `config/profile.yaml`; matching is in `extract/role.py`.
- Locations: India (any city, but **hide onsite-only roles in Bengaluru and Hyderabad**; hybrid/remote there is fine), remote-global, and Europe/US **only if visa sponsorship is offered or relocation is explicit**.
- Skills to match against (edit in `config/profile.yaml`): Python, PyTorch, FastAPI, LLMs, knowledge distillation, speculative decoding, CUDA kernels, agents/evals. Add the real resume list there.

## Pipeline (high level)
1. **Discover** companies and their ATS (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, plus YC and Hacker News "Who is hiring").
2. **Fetch** postings via each ATS's public JSON endpoint on a schedule.
3. **Normalize** to one schema (see below). Dedupe.
4. **Extract** experience, batch year, location type, visa sponsorship, skills via rules first, LLM only for ambiguous cases (see `skills.md`).
5. **Classify** into `fresher` / `maybe` / `experienced` with confidence + evidence.
6. **Publish** classified jobs to D1; the web page reads them through the Python API (see `docs/decisions.md`). New postings are flagged with first-seen time.

## Core schema (starting point; propose changes via decisions.md)
`id`, `source`, `company`, `title`, `url`, `location_raw`, `location_type` (remote/hybrid/onsite), `countries`, `posted_at` (if the source gives it), `first_seen_at`, `description_text`, `yoe_min`, `yoe_max`, `yoe_evidence`, `batch_years`, `level` (fresher/maybe/experienced), `level_confidence`, `visa_sponsorship` (yes/no/unknown), `skills`, `match_score`, `status` (open/closed), `content_hash`.

## Architecture (decided; full rationale in `docs/decisions.md`)
- Pipeline: Python, run by GitHub Actions cron
- Storage: Cloudflare D1 (free tier: 100k rows written/day, so write only new/changed rows)
- Backend API: FastAPI on Cloudflare Python Workers, D1 binding
- Frontend: React (Vite + TypeScript), served by the same Worker via Workers Static Assets
- LLM: none in the pipeline (rules only). An optional, off-by-default "Check my fit" button calls Gemini from the API for one job at a time (see `docs/decisions.md`)
- Companies: curated list in `config/companies.yaml`, plus hiring YC AI startups imported from the yc-oss dataset (`scripts/import_yc.py`); only verified boards are fetched
- Any change to the above is a new decision: present options, let Shrey choose, log it.

## Suggested build order
1. Curated list of ~200 companies (incl. YC) + Greenhouse/Lever/Ashby fetchers → normalized JSON
2. Rule-based YoE and batch-year extractor with a test suite built from real postings
3. FastAPI backend + React page with filters (level, location type, visa, skills) and a "new in last 24h" view
4. Scheduler + publish loop
5. LLM fallback for `maybe` cases, with an eval set to measure it
6. More sources (YC, HN, company career pages), match scoring, optional alerts

## Testing and quality
- Keep a labeled fixture set in `tests/fixtures/` (real job descriptions + expected level). Every extraction bug becomes a new fixture first, then a fix.
- Track precision of the `fresher` bucket on the fixtures; it must not regress.
- Never mark a job `fresher` when any explicit requirement of 2+ years exists in the description, even if the title says "Associate" or "Junior".

## Conventions
- Keep modules small: one adapter per source in `sources/`, extraction in `extract/`, nothing source-specific leaks outside adapters.
- Config in `config/` (profile, company list, keyword lists), not hardcoded.
- Prefer boring, readable code with type hints. Comment the why, not the what.