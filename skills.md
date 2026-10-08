# skills.md — Reusable procedures for the job board repo

Claude: read the relevant skill before doing that kind of task. Each skill says when to use it, the steps, and the checks. (Claude Code natively loads skills from `.claude/skills/<name>/SKILL.md`; each section below can be split out into that layout later.)

---

## 1. Add a new job source adapter
**Use when:** adding a new ATS, aggregator, or company career page.

Steps:
1. Check for an official public API or feed first (JSON endpoint, RSS, sitemap). HTML scraping is the last resort. Check robots.txt and ToS; skip the source if it forbids automated access.
2. Known public endpoints to try before anything else:
   - Greenhouse: `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`
   - Lever: `api.lever.co/v0/postings/{company}?mode=json`
   - Ashby: `api.ashbyhq.com/posting-api/job-board/{company}`
   - Workable / SmartRecruiters: public widget or posting APIs
   - Hacker News "Who is hiring": monthly thread via the HN Firebase/Algolia API
   - YC jobs: only through publicly reachable pages; do not bypass login walls
3. Write one adapter in `sources/` that returns the normalized schema from CLAUDE.md. No extraction logic inside adapters.
4. Add polite fetching: User-Agent, per-host rate limit, ETag/If-Modified-Since, retry with backoff.
5. Save 3 real sample responses to `tests/fixtures/` and write a test that parses them.
6. Log a decision entry if the source needed a tradeoff (e.g. HTML parsing).

Done when: adapter returns normalized jobs, tests pass, and a second run only reports truly new postings.

---

## 2. Extract years of experience (YoE) accurately
**Use when:** touching anything that decides fresher vs experienced. This is the most important skill in the repo.

Approach: **rules first, LLM only for what rules cannot settle.**

Rule layer (run on the full description text, not just the title):
- Capture patterns such as: `3+ years`, `2-4 years`, `at least 5 years`, `minimum of 2 years`, `2 to 3 yrs`, `3 years of experience`, `five years`, `0-1 years`, `1 year`, `no experience required`, `fresh graduates welcome`.
- Handle number words (one..ten), ranges, and "X+" forms. Record `yoe_min`, `yoe_max`, and the exact evidence sentence.
- Scope the number: "5 years of company history" or "3 years of funding" is not a requirement. Only count a number when it is near experience words (experience, working with, of hands-on, in a similar role). Prefer sentences inside requirements/qualifications sections.
- Separate **required** from **preferred/nice-to-have**. A preferred "2+ years" should lower confidence, not auto-reject.
- Detect fresher signals: `new grad`, `graduate`, `campus`, `entry level`, `0-1 year`, `2026 batch`, `class of 2026`, `recent graduate`. Detect batch years and check they include 2026 (or are open).
- Detect negative signals even when the title looks junior: `senior`, `staff`, `lead`, `principal`, `manager`, and any required YoE >= 2.

Decision table:
- `fresher`: explicit fresher/batch signal OR required YoE max <= 1, AND no required YoE >= 2 anywhere.
- `experienced`: any required YoE min >= 2, or senior-style title.
- `maybe`: no YoE stated and no fresher signal, or conflicting signals. Show in a separate tab, never mixed into `fresher`.

LLM: none in the pipeline (removed 2026-10-08). Gemini is only an opt-in, per-job "Check my fit" in the API (`api/src/fit.py`), off unless the Worker sets `FIT_CHECK=on`.

Checks: every new misclassification becomes a fixture in `tests/fixtures/labeled/postings.jsonl` first. Report precision on the `fresher` bucket after any change: `python scripts/eval_extractor.py` (exits non-zero if fresher precision drops below 100%). Code lives in `extract/` (`sections.py` → clauses with preferred/required section, `yoe.py`, `signals.py`, `classify.py`).

---

## 3. Classify location and visa sponsorship
**Use when:** filtering by geography.

Steps:
1. Normalize location to `location_type` (remote / hybrid / onsite) and a country list. Countries: `extract/location.py` with aliases in `config/locations.yaml` (add cities/spellings there, not in code). "Remote" must be checked for geo restrictions ("US only", "EU timezones") before counting as remote-global.
2. India: keep all cities except **onsite-only Bengaluru and Hyderabad** (configurable in `config/profile.yaml`).
3. Europe/US: keep only if the text indicates sponsorship or relocation help (`visa sponsorship`, `we sponsor`, `relocation assistance`, `Blue Card`, `H-1B`). Explicit negatives (`no sponsorship`, `must be authorized to work`, `no visa`) set `visa_sponsorship = no` and hide the job.
4. Unknown sponsorship for Europe/US → `unknown`, hidden by default, visible with a filter toggle.
5. Store the evidence snippet for every decision.

---

## 4. Dedupe and detect new postings
**Use when:** ingesting any batch of jobs.

Steps:
1. Primary key: `source + external_id`. Secondary key: hash of normalized `company + title + location + canonical_url` to catch cross-posted jobs.
2. `first_seen_at` is set once and never overwritten. That timestamp, not the source's `posted_at`, drives the "new" badge (many sources have no reliable post date).
3. A job missing from a later fetch of its source is marked `closed`, not deleted.
4. If `content_hash` changes, re-run extraction.

---

## 5. Match scoring against the profile
**Use when:** ranking jobs.

Steps:
1. Start with a transparent keyword score using skills from `config/profile.yaml` (title match, required-skills overlap, stack overlap).
2. Show why a job scored high (matched skills list). No black-box scores.
3. Only consider embeddings or an LLM after the keyword score is working and measured. Free-tier limits apply.

---

## 6. Build and update the web page
**Use when:** working on the UI.

Steps:
1. Page (React on Cloudflare Pages) reads jobs from the FastAPI backend on Cloudflare Python Workers, which queries D1. See `docs/decisions.md`.
2. The page lists every open job, newest first, 20 per page. Filters: experience (fresher, internship, 0–N yrs, not stated, experienced), role, company, country/city, work mode, posted, and "only where I can work" (location/visa rules). Filter lists come from the `meta` snapshot publish writes; keep list queries on `idx_jobs_recent`/`idx_jobs_level` (`api/src/queries.py`).
3. Each card shows: title, company, location type, level badge with confidence, matched skills, and an "evidence" expander showing why it was labeled fresher (the quoted snippet).
4. Mobile-friendly, fast, no heavy framework unless chosen in decisions.md. Check accessibility basics.

---

## 7. Schedule and publish (free tier safe)
**Use when:** automating runs.

Steps:
1. Propose scheduler options with limits (e.g. GitHub Actions cron granularity and monthly minutes, Cloudflare cron limits) and let Shrey choose.
2. Run fetch → normalize → extract → classify → publish JSON in one job. Fail loudly per source; one broken source must not block the others.
3. Store secrets only in the platform's secret store, never in the repo.
4. After each run, write a short run summary: jobs fetched, new, closed, per-source errors.

---

## 8. Debug a wrong classification
**Use when:** Shrey reports "this job shows as fresher but needs 3 years" (or the reverse).

Steps:
1. Save the job's full description as a fixture with the expected label.
2. Run the extractor and read the stored evidence to see which rule fired or missed.
3. Fix the rule or add a pattern. Do not special-case the single job.
4. Re-run `python scripts/eval_extractor.py` and `pytest`; report fresher precision before and after.