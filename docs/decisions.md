# Architecture decisions

Newest first. Each entry: date, options considered, choice, why.

---

## 2026-10-07 — Gemini model name, and failed calls
- **Found:** with the key added, every call to `gemini-2.5-flash-lite` answered HTTP 404. The model is still listed, but its Cloud retirement is 2026-10-20 and Google no longer serves it to this key. The first eval reported a false 100%, because unanswered calls counted as "no usable answer". The pipeline would also have cached those failures and never asked again.
- **Fix:** try `gemini-3.5-flash-lite`, then `gemini-3.1-flash-lite`, then `gemini-2.5-flash-lite`, moving on at each 404 (`GEMINI_MODEL` overrides the list). Still the Flash-Lite tier Shrey chose, so the free-tier limits above apply; check AI Studio's rate-limit page for the exact numbers per model. Failed calls are never cached. Three failures in a row stop that run's reviews. The eval now fails unless every call gets an answer.

## 2026-10-07 — LLM second opinion for `maybe` jobs (build step 5)
- **Options:** Gemini 2.5 Flash-Lite free tier · Groq Llama 3.3 70B free tier · both, with Groq as backup
- **Choice (Shrey):** Gemini. Replaces "rules-only for now" (2026-10-05).
- **How it's kept precise:** the rules run first, and only `maybe` jobs the page would show go to the model. Its answer must quote the posting verbatim (checked; quotes under 12 characters rejected). A required 2+ years makes the job `experienced`. A stated number fills `yoe_min` for the 0–N filters; the stored minimum is only ever raised. `fresher` is allowed only when the rules found no experience mention at all, and gets confidence 0.6 with the quote as evidence. Explicit requirements found by the rules are never overridden.
- **Limits (free tier, checked 2026-10-07; Google has cut these before):** about 15 requests/min and 1,000/day. We use at most 100 requests a run (8 runs a day), one every 4.5 s, and stop at the first 429. Verdicts are cached per `content_hash` in the Actions cache, so the ~500-job backlog clears in about 5 runs and later runs ask only about new postings. Free-tier prompts may be used by Google; the postings are public.
- **Gate:** `scripts/eval_llm.py` (the "LLM eval" workflow) runs rules + Gemini on the labeled postings and fails below 100% fresher precision. The labeled set has only 8 `maybe` cases, so it should grow with real `maybe` postings.
- **Needs:** a `GEMINI_API_KEY` repo secret, from aistudio.google.com. Without it the pipeline stays rules-only.

## 2026-10-07 — Indian fintech, e-commerce and consultancies
- **Asked (Shrey):** more Indian fintech, consultancy (Accenture, Deloitte...), startup and e-commerce companies.
- **Added (18, on careers systems we already fetch):** BharatPe, Pine Labs, MobiKwik, Go Digit, smallcase, BigBasket, Delhivery, Rapido (Darwinbox); Upstox, Fi (Lever); Dhan (Keka); Myntra (Greenhouse); Tiger Analytics (Workable); Accenture, PwC campus, Genpact, Cognizant (Workday); Publicis Sapient (SmartRecruiters). Global consultancies are `india_only`. Dream11 retried under the `dream11` Lever slug.
- **Left out, unsupported systems:** SuccessFactors (EY, Capgemini, HCLTech, Wipro, Globant), Avature (Deloitte USI, IBM), Oracle HCM (KPMG, EXL), Kula (Cashfree, Acko), TurboHire (Navi, skipped earlier), PeopleStrong (MathCo), MyNextHire (ShareChat), Skima (Nykaa), and custom portals (Infosys, TCS, Flipkart, Zerodha, Juspay, Urban Company, Udaan...). Some only take email or LinkedIn applications. SuccessFactors and Oracle HCM cover the most of these and are worth a separate adapter decision later.
- **Caveat:** Darwinbox refuses GitHub's runners (403), so those 8 stay unverified until that changes.

## 2026-10-07 — Discovering companies automatically, and the default view
- **Discovery sources. Options:** new YC batches (yc-oss) · board links in HN "Who is hiring?" posts · GitHub new-grad lists (e.g. SimplifyJobs)
- **Choice (Shrey):** new YC batches and HN board links. `scripts/discover_companies.py` collects candidates from both, probes each board live, and keeps only boards with at least one title that could be a target role.
- **Approval. Options:** a PR per batch · straight to main · a weekly report only
- **Choice (Shrey):** a PR once a batch has 10–20 companies. The weekly workflow (`discover-companies.yml`, Mondays) writes nothing below 10, adds at most 20 (most AI/ML titles first), and opens no second PR while one is open. The run keeps no state: rejected candidates are probed again the next week, capped at 200 candidates a run.
- **Limits:** the repo setting "Allow GitHub Actions to create and approve pull requests" must be on. PRs opened by the workflow's token don't trigger other workflows, so boards are verified before the PR opens. The YC filter is unchanged (team ≥ 10 or India-based), so a tiny new-batch startup is picked up once it grows.
- **Default view (Shrey):** the page opens on "All levels" instead of "Fresher". Many entry-level posts state no years, so the reader narrows to 0–1, 0–2, 0–3 or Not stated. Only target roles are listed, as before; the fresher rules are unchanged.

## 2026-10-07 — Old postings, and hiring outside company boards
- **Old postings. Options:** hide when posted > 60 days ago and show the date · hide > 30 days · only show the date
- **Choice (Shrey):** hide postings older than 30 days when the source gives a posting date; undated jobs stay. Lists sort by posting date and cards show "Posted 3 days ago". Before this, a job stayed listed for as long as its company left it on the board.
- **Other channels. Options:** HN "Who is hiring" (official API) · paste-a-job form · Reddit hiring threads (free app key) · job-alert emails from Gmail. LinkedIn/Indeed/Glassdoor scraping, X (paid API), Wellfound and YC Work at a Startup (no API, ToS) ruled out.
- **Choice (Shrey):** HN "Who is hiring" only, for now: the latest monthly thread through hn.algolia.com, one job per top-level post using the "Company | Role | Place" header convention.

## 2026-10-06 — Stay inside D1's daily write limit
- **What happened:** the 100k rows written/day limit was hit. Each extractor-version bump rewrote all ~14k stored jobs (cities, then visa/eligibility), on top of the first full insert; index updates count too.
- **Options:** store only target-role jobs (~20x fewer rows) · keep everything and write smarter
- **Choice (Shrey):** keep everything. Re-extraction now writes only rows whose extracted values changed (`extract_hash`, migration 0004), and each run writes at most 12k rows (new jobs first, then changed/reopened, re-extracted, closings); the rest waits for the next run.
- **Why:** keeping every job means a role type added to the profile later instantly reveals older matching jobs.

## 2026-10-06 — TurboHire (Flipkart, Ola, Setu, Urban Company, IDfy): not built
- **Finding:** the careers hosts' robots.txt disallows all bots except Googlebot, and the job API needs a token that's only issued to requests claiming to come from TurboHire's own site (a forged Referer).
- **Choice:** skip. CLAUDE.md requires respecting robots.txt and ToS, and faking a Referer is working around access control. Today these boards held ~37 open jobs in total (Flipkart 7, IDfy 19, Urban Company 11; Ola and Pine Labs/Setu 0).

## 2026-10-06 — Android and React Native roles; MNCs; visa rule for roles abroad
- **Mobile roles. Options:** native Android only · Android + Flutter · all mobile · *(Shrey's choice)* Android + React Native
- **Choice:** Android and React Native count as a `mobile` role family. iOS-only and Flutter stay excluded. A title naming Android/React Native beats the iOS/mobile excludes; generic "Mobile Engineer" titles need an Android/React Native stack in the description. The page gets a Role dropdown.
- **MNC locations. Options:** India + remote only · all locations · *(Shrey's choice)* India + remote, and roles abroad only when the posting sponsors visas
- **Choice:** large MNC boards fetch only India and remote roles. For every company, a role outside India (and not remote-anywhere) is shown only when its description offers visa sponsorship or relocation — the profile rule that wasn't enforced until now. Onsite-only roles in Bengaluru/Hyderabad are hidden at the same time.
- **MNC sources. Options:** Workday + Amazon + Eightfold · only systems already supported
- **Choice:** Workday + Amazon + Eightfold (Microsoft, PayPal, Qualcomm…). Google has no public jobs API and is skipped.

## 2026-10-06 — Scheduled fetch (build step 4)
- **Options:** every hour · every 3 hours · every 6 hours
- **Choice:** Every 3 hours (cron `17 */3 * * *`, off the top of the hour because GitHub delays on-the-hour runs most).
- **Closing rule:** a job is closed after it is missing from its board on **2 runs in a row**, and only when that board fetched OK. One flaky response no longer hides a live job.
- **Keep-alive:** each run re-enables its own workflow through the GitHub API, which resets GitHub's 60-day inactivity timer for scheduled workflows.
- **Limits:** public repo, so Actions minutes are free; ~8 runs × ~6 min a day. D1 writes stay far under 100k/day because unchanged jobs are not written.

## 2026-10-06 — Indian cities and a City filter
- **Options:** more Indian city aliases only · a City dropdown for India only · both
- **Choice:** Both. Schema gains a `cities` column (JSON array of Indian cities found in the location).
- **Why:** Smaller cities (Mysuru, Vizag, Mohali…) were not mapped to India, and "India" alone is too coarse for picking where to live. Cities are only extracted for India, where the profile cares.

## 2026-10-06 — More YC startups from the yc-oss dataset
- **Options:** yc-oss dataset (community JSON mirror of the YC directory on GitHub) · Claude hand-picks
- **Choice:** yc-oss dataset, filtered to active, hiring, AI-tagged companies from batch 2021 on with 10+ people (or based in India), then verified against the ATSs like every other company. First import: 234 companies.
- **Why:** Covers recent batches without scraping YC's site or the login-walled Work at a Startup. Supersedes the "~200 companies" target: the list grows past it, still with only verified boards fetched.

## 2026-10-06 — Indian companies outside Greenhouse/Lever/Ashby
- **Options:** new ATS adapters + schema.org JSON-LD fallback · one scraper per company · ATS adapters only
- **Choice:** ATS adapters for job systems common in India that publish public job data, plus a generic reader for the schema.org `JobPosting` JSON-LD that careers pages embed for Google Jobs.
- **Why:** One adapter covers many companies and breaks rarely; per-company HTML scrapers break whenever a site changes. Survey which system each unverified Indian company uses first, then build only the adapters that cover several companies. robots.txt is checked before any careers page is read.
- **Survey result (41 unverified Indian companies + 45 proposed):** Darwinbox 11, Workday 6, Zoho Recruit 3, Keka 3; TurboHire 5 (Flipkart, Ola, Setu, Urban Company, IDfy); a long tail of one-company systems; JSON-LD on job pages at only 3 sites.
- **Built:** Workday (public sitemap + per-job JSON), Darwinbox (paged list + per-job JSON), Keka (one JSON list), Zoho Recruit (jobs embedded in the careers page). Workday and Darwinbox need one request per job, so they only fetch jobs whose title could be a target role (`sources/prefilter.py`). Keka's and Darwinbox's structured experience fields become an "Experience: 3-5 years" line so the YoE rules use them as evidence.
- **Live check from GitHub Actions (2026-10-06):** Workday, Keka and Zoho Recruit work. **Darwinbox answers 403 to GitHub's runners** (it answered other networks), so its 11 companies stay unverified and aren't fetched; we don't work around a block. Keka's portal id isn't on its careers page from the runners, so Keka slugs carry it ("sub/guid"); nference and Signzy need theirs found.
- **Deferred:** the JSON-LD reader (3 sites isn't worth it yet) and TurboHire (endpoint not researched; next candidate, covers Flipkart and Ola).

## 2026-10-06 — Serve React from the API Worker (Workers Static Assets) instead of Cloudflare Pages
- **Options:** one Python Worker serving FastAPI + the React build · React on Pages + separate API Worker
- **Choice:** One Worker. Supersedes the "Cloudflare Pages" part of the frontend decision below.
- **Why:** One deploy and one URL, no CORS. Static asset requests are free and don't count toward Workers' 100k requests/day; only `/api/*` calls run Python. Cloudflare now recommends Static Assets over Pages for new projects.

## 2026-10-06 — Count plain "Software Engineer" titles when the work is Python + AI (confirmed by Shrey 2026-10-07)
- **Options:** only AI/ML and backend titles · also plain SWE titles whose description shows Python and AI/ML work
- **Choice (toggle in `config/profile.yaml` → `generic_swe.enabled`):** include them. Confirmed by Shrey.
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
