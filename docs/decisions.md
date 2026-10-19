# Architecture decisions

Newest first. Each entry: date, options considered, choice, why.

---

## 2026-10-19 — Big global boards are read once a day
- **Options:** every board every 3 hours (as before) · the big global boards (`india_only`) once a
  day, everyone else every 3 hours
- **Choice (Shrey):** once a day for the 88 `india_only` boards (Workday 46, career sites 13, Oracle,
  Eightfold, Amazon...), at 03:17 UTC (08:47 IST, so the morning list is fresh); the 7 other runs
  pass `--skip-global`. A manual run reads everything.
- **Why:** these boards list thousands of jobs that change slowly and need one request per job, so
  they take most of each run's time and load on their hosts; startup boards change by the hour.
- **Safe:** a skipped board is missing from `boards_ok`, so `publish_pg.py` neither closes nor
  touches its jobs. A job on a big board now closes after 2 daily misses instead of 2 runs.

## 2026-10-19 — Salary range on the page
- **Options:** a new salary column (pulled out at fetch time, via a migration) · keep the pay line in
  the stored description; where it shows: detail view and list rows · detail view only
- **Choice (Shrey):** keep it in the text, show it in both places. `extract/stored_text.py` puts the
  posting's stated range on a "Salary" line at the top of the stored description; the API reads that
  line in SQL (`substring(... '^Salary\n...')`), so list pages still never carry the description.
- **Why:** no schema change. Cost: pay can't be filtered or sorted until it gets its own column.
- **Rule:** only a stated range with a currency or LPA, on a line about pay or a line that is just
  the range; a single amount only when the line says salary, stipend or CTC. Deal sizes, funding
  rounds and loan amounts never count (precision over recall). Several ranges by location: the first,
  plus "(+N more by location)".

## 2026-10-19 — Weekly careers detection lands as a PR
- **Options:** a weekly PR from a bot branch · upload the report only, applied in a later session ·
  let the bot push straight to the protected `main`
- **Choice (Shrey):** weekly PR. `.github/workflows/detect-careers-weekly.yml` runs Mondays 03:13 UTC,
  reads every company without a readable board, verifies what it finds, and opens one PR on
  `auto/careers-detection` listing only boards that changed or became readable.
- **Why:** detection has picked wrong boards before (Moveworks onto ServiceNow's, six YC companies
  onto ycombinator.com), so a person checks each change before it goes live. "Report only" would
  leave new boards waiting for a session; pushing to `main` would skip that check.
- **Limits:** needs "Allow GitHub Actions to create and approve pull requests" (already on for
  discovery). A PR opened with `GITHUB_TOKEN` doesn't run the other workflows, so the boards are
  verified inside the weekly run. While a detection PR is open, the next week's run is skipped.

## 2026-10-18 — Company coverage strategy (`docs/strategy/company-coverage.md`)
- **Context:** 237 of 612 companies were never found on the shared job boards: they recruit on
  their own careers sites (Workday, SuccessFactors, iCIMS...). Many are foreign companies hiring
  through India offices (1,700+ GCCs, Nasscom FY2024).
- **1. Order (Shrey: Claude's proposal):**
  - **A** (now): re-check the 237; add company websites; build a careers-system detector
  - **B:** India GCC lists + Wikidata websites
  - **D:** new adapters for SuccessFactors, Phenom, iCIMS, Taleo
  - **C:** the Common Crawl index of careers-system addresses
  - **E:** GitHub new-grad lists
  - **Why this order:** India offices first, because they are the audience's employers; the
    adapters before the bulk sweep, because C mostly finds MNC systems we can't read yet.
- **2. What we store (Shrey's own option, chosen over "full text only for target roles"):**
  - Store three sections per job, not the whole description: **About the role**, **Required**
    and **Preferred** skills. The full posting stays one click away on the company's site.
  - **Rule:** the experience, batch and role extractors still read the full text first, and
    keep their evidence snippets, so precision does not drop.
  - **Why:**
    - storage drops for every job, not just some
    - the page shows what a student needs to decide
    - we don't republish companies' full postings
- **3. Global companies (Shrey: Claude's pick):** from MNC careers sites, keep only India,
  remote, and visa/relocation jobs.
  - **Why:** these are the jobs Kario's users can take.
  - It also keeps MNC tenants with thousands of global jobs inside the run-time and storage
    limits.

---

## 2026-10-17 — Switch-over to the Next.js site (M4.6)
- **What changed:**
  - The Worker now serves `site/out` (the Next.js static export) instead of `web/dist`.
  - Deploys build `site/`.
  - The Tests workflow gained a `site` job: lint, types, design-token sync and the build.
- **Unknown paths:**
  - **Options:** keep `single-page-application` (every unknown URL shows the home page with a 200), or use `404-page`.
  - **Choice:** `404-page`, with a branded `not-found` page.
  - **Why:** Next exports one HTML file per page, so a wrong link should say so honestly. A 200 for every URL also confuses search engines and link checkers.
- **Rollback:** `web/` stays in the repo until the new site is confirmed live. Going back is a one-line change of `assets.directory` plus the deploy path. Delete `web/` after that.
- **Confirmed live (Shrey, 2026-10-17):** `web/` deleted. Rollback from here means reverting PR #35 from git history.
- **Built in small steps (Shrey chose to learn step by step):**
  1. scaffold
  2. tokens
  3. live data
  4. split view
  5. filters
  6. switch-over
- **Measured:** 140.5 KB gzipped JS on the job page against the ~170 KB budget. React and the Next runtime are 132 KB of that.

---

## 2026-10-17 — Logo: outlined Instrument Serif wordmark; M4.5 look approved
- **Options:**
  - load Instrument Serif as a third font, just for the wordmark
  - outline the wordmark into an SVG logo
- **Choice (Shrey):** the SVG logo (`brand/kario-wordmark.svg`), plus a square "k" mark
  (`brand/kario-mark.svg`) for the favicon and app icon.
- **Why:** it keeps the site at two font families, as `CLAUDE.md` requires. It also saves a
  font download on budget phones, and the logo looks the same everywhere.
- **Licence:** Instrument Serif is under the SIL Open Font License, which allows using it in a
  logo.
- **Status:** Shrey approved the workspace look (`docs/wireframes/workspace.html`). M4.5 is done;
  the next step is the Next.js scaffold (M4.6).

---

## 2026-10-17 — Visual direction: split-pane workspace, white + purple (M4.5)
- **Options shown:** the split view in three styles (Midnight dark/lime, Paper light/mono, Bold
  warm/orange).
- **Choice (Shrey, his own spec):**
  - the warm alabaster canvas `#F7F6F2` with a forest-obsidian accent `#0F221A`
  - one sticky 56 px header: serif wordmark, view tabs, search with a `/` shortcut
  - filter chips with an 8 px radius and key–value text (`YOE ≤ 3 yrs`)
  - one continuous list panel (no floating cards); the selected row gets a soft fill and an
    animated 3 px forest bar
  - j/k and arrow-key navigation
  - a sticky details panel with a dark forest card: the big years number, the quoted evidence,
    and a fit checklist
  - forest Apply button, Save and Hide, with A/S/H shortcuts
  - real Requirements, Tech stack and Responsibilities sections plus the source ATS, never grey
    placeholder bars
  - no "Fits your N years" label
- **Why over the three styles:** it keeps Paper's calm, readable list and brings back the
  high-contrast "why it fits" card, so the one thing Kario is for (trustworthy labels) is the
  loudest element on the screen.
- **Honesty rules kept:**
  - The checklist only shows what the extractor found. Missing facts show as a grey dash ("Batch
    not stated", "Visa not mentioned"), never a tick.
  - Tech terms are only those named in the posting.
  - There are no match percentages.
- **Revision, same day (Shrey):**
  - Palette is now a white background, near-black text `#0A0A12`, and one Stripe-like purple
    accent. It replaces the alabaster and forest.
  - The purple is `#5851EC`, a shade darker than Stripe's `#635BFF`. `#635BFF` only reaches
    4.3:1 on the selected-row tint; `#5851EC` reaches 5.1:1 or better, which passes WCAG AA.
  - The fit card is near-black with a light-purple accent `#A5A0FF` (8.5:1).
  - All labels are in sentence case ("Experience", "Requirements"), not capitals.
  - Job titles are medium weight, not semibold.
  - Years in the list are plain coloured text, without a box.
  - The accent is solid colour only; `CLAUDE.md` bans purple gradients.
- **Second revision, same day (Shrey):**
  - No boxes: the details panel sits on the page, and a single vertical line separates it from
    the list.
  - The list has no row dividers; the selected row keeps its tint and accent bar.
  - Company logos replace the letter boxes. In the prototype they load from Google's favicon
    service, with a plain letter as the fallback.
  - In production the pipeline will fetch each company's logo once and store it with our own
    assets, so pages never call a third party (privacy, speed).
  - "For you", "Saved" and "Applied" moved into the profile menu, under the avatar.
- **Prototype:** `docs/wireframes/workspace.html`. Static HTML with Tailwind's browser build; the
  Next.js port (M4.6) uses `motion/react` `layoutId` for the row bar.
- **Open:** `CLAUDE.md` allows at most two font families. This uses Geist and Geist Mono, plus
  Instrument Serif for the wordmark only. Treat the wordmark as a logo (an SVG) so the rule
  holds.

---

## 2026-10-17 — Job-list layout: split view (M4.4)
- **Rounds:**
  1. A plain card list. Shrey: too boxy, wrong shape, too wordy.
  2. Ledger, Experience rail, Inbox.
  3. Three options built from patterns in Shrey's reference products (Jobright, Careerlift,
     Tsenta): a fit-panel card, a dark board grid, and a split view.
- **Choice (Shrey):** split view: a list plus a details panel; on phones the details open
  full-screen.
- **Why over the others:**
  - The most jobs per screen (~8 on a phone, against ~2.5 and ~3.5).
  - The years badge stays on every row.
  - The evidence gets a large, readable place in the details, which matches "evidence behind a
    tap".
  - The fit-panel cards were the most distinctive but meant the most scrolling. The board grid
    showed evidence on every card, against the brief, and a grid is harder to compare down.
- **Kept out on purpose:** match percentages (we don't compute a real one), upsell banners,
  sparkle icons, salary (not extracted yet).

---

## 2026-10-16 — Audience: every experience level, not only freshers
- **Options:**
  - keep the product fresher-only
  - cover every experience level, with a "My experience" filter
- **Choice (Shrey):** all experience levels. Freshers stay a core group.
- **Why:** the pipeline already labels every job's years (yoe_min/yoe_max with evidence), so a
  wider audience costs no new data work. A student who gets a job keeps using Kario a year
  later instead of leaving.
- **What doesn't change:** precision over recall. The rule generalises: a job whose stated
  minimum is above the user's years never shows to them, and a job with no stated years is
  tagged "Not stated", never entry-level.

---

## 2026-10-16 — Name: Kario (M4.1)
- **Options:** Batchmate (Claude's pick), ZeroYears, Firstrole, keep frshmen, Kario (Shrey's).
- **Choice (Shrey):** Kario.
- **Why over the others:**
  - Short and easy to type on a phone; it echoes "career" and the Hindi "karo" ("do it").
  - Batchmate and ZeroYears say "fresher", which no longer fits now that the audience spans
    experience levels (entry above).
  - frshmen is hard to spell when said aloud.
- **Cost:** the name doesn't explain itself, so the tagline must say what Kario does.
  Pronunciation is ambiguous (KAR-ee-oh vs KAI-ree-oh); pick one and use it everywhere.
- **Before launch:** Shrey checks the domain and the Indian trademark register. A quick web
  search found no jobs product with this name (the nearest is Clario, a clinical-trials company).

---

## 2026-10-16 — Where the Next.js site runs (M4)
- **Options:**
  - A: static export (`output: "export"`) served by the existing Worker next to `/api`
  - B: full Next.js on Cloudflare Workers via OpenNext, with server rendering
  - C: Vercel Hobby
- **Choice (Shrey):** A. When shareable job pages arrive, the Python Worker will add each job's Open Graph tags to `/jobs/{id}` before serving the static page.
- **Why:**
  - Nothing new to run, and plain files are the fastest for students on budget phones.
  - The main reason for B was link preview cards (WhatsApp/LinkedIn bots read the HTML and don't run JavaScript). The Worker adding the tags covers that at a fraction of the moving parts.
  - B adds a second Worker and a 3 MB free-plan size limit.
  - C is ruled out: Vercel Hobby is for non-commercial personal use only, and this will be a company.
- **Revisit:** if whole pages need server rendering, such as personalised pages or search pages that Google must index, move to B; the design work carries over.

---

## 2026-10-16 — D1 retired from the pipeline (M3 done)
- **Options:**
  - stop writing D1 and delete it now
  - stop writing D1 now, keep the database a week as a backup, then delete it
- **Choice (Shrey):** stop writes now; keep the D1 database until ~2026-10-23, then delete it in the Cloudflare dashboard.
- **Why:** the site has run on Supabase since the API switch and Shrey confirmed it works. A week-old copy costs nothing and covers a surprise. Dual-writing longer would only cost run time.
- **Removed:**
  - `publish_d1.py`, the D1 `db/migrations/` and the SQLite `queries.py`
  - the one-off copy script and its workflow
  - the D1 binding and its deploy step
- **Kept:** the row mapping, which moved to `scripts/job_rows.py`. The publisher's D1 tests were ported to run against Postgres in CI.

---

## 2026-10-16 — API switch to Supabase: how it reads (M3)
- **Driver options** (Cloudflare's tested list for Python Workers + Hyperdrive): asyncpg, pg8000, psycopg.
- **Choice:** asyncpg.
- **Why:** it's Cloudflare's recommended driver, and it's async, which suits FastAPI. One connection per request is cheap because Hyperdrive keeps the pool to Supabase open.
- **What the API reads:** a `job_cards` view (jobs + company name + current label), so the API stays one simple `SELECT` per page.
- **Finding each job's current label — options:**
  - `DISTINCT ON` / a per-job lookup on every query
  - an `is_current` flag on `job_labels` that the pipeline keeps
- **Choice:** the flag (`db/postgres/0003_job_cards.sql`).
- **Why:** measured on 27k jobs, a filtered count took ~3 s with the per-job lookup and 23 ms with the flag; the filter snapshot went from 2.3 s to 0.4 s. A page of 20 takes under 10 ms either way. A unique index allows at most one current label per job.
- **Keeping the D1 code path in the API — options:**
  - keep both D1 and Postgres SQL behind a switch
  - Postgres only
- **Choice:** Postgres only.
- **Why:** the SQL differs (arrays, `ILIKE`, booleans), so two copies would drift. Rollback stays easy: D1 is still fed by the dual-write, so reverting the PR puts the site back on D1 within one deploy.

---

## 2026-10-16 — Switching from D1 to Supabase: order and dual-write (M3)
- **Order options:**
  - switch the API first, then the pipeline
  - switch the pipeline first, then the API
- **Choice (Shrey):** pipeline first.
- **Why:** an API reading Supabase would show a database that has stopped receiving new jobs; the pipeline has to fill Supabase before anything reads it.
- **Gap options (between the two switches):**
  - stop writing D1 as soon as the pipeline moves
  - dual-write: the pipeline writes to both D1 and Supabase until the API has moved
- **Choice (Shrey):** dual-write.
- **Why:** with D1 writes stopped, the live site (still reading D1) would freeze until the API rewrite ships, possibly for days. Dual-writing keeps the site fresh, means the API switch has no downtime, and allows a rollback at any point by pointing the API back at D1.
- **Cost:** each pipeline run takes a few minutes longer. D1's write budget is unchanged (the same writes as before).
- **Steps:**
  1. Pipeline writes D1 + Supabase.
  2. API reads Supabase through Hyperdrive.
  3. Drop the D1 write, then D1 itself.

---

## 2026-10-16 — How the one-off D1 → Supabase copy works (M3)
- **Options:**
  - one big transaction for all ~27k jobs
  - small batches (500 jobs) in their own transactions, with upserts
- **Choice (Shrey's design):** small batches + upserts by stable id, skipping unchanged rows (`content_hash`, `label_hash`), with a count check per status, level and company at the end.
- **Why:**
  - One transaction would roll back all the work if the connection dropped near the end.
  - Batches lose at most one batch, and the upserts make a re-run safe: running twice gives the same result as once. The 3-hourly pipeline relies on the same rule.
  - The count check proves nothing was lost before anything switches over.
- **Result:** 27,243 jobs in 55 batches, counts matched (run on 2026-10-16).

---

## 2026-10-16 — Reposted jobs (schema, M3)
- **Problem:** a company re-lists the same role under a new ATS id. The pipeline sees a new job, and if the old listing is still up, students see two cards and applications split across them.
- **Shrey's rules:** one card, showing today's date; applications on the old listing stay on the merged job.
- **Options:**
  - A: keep the original row and record the new listing's id in a `job_aliases` table
  - B: create a row for the new listing, move applications over, close the old row
- **Choice (Shrey):** A.
- **Why:** nothing students or the rules depend on moves: applications, labels and `first_seen_at` stay put. B breaks the one-application-per-student-per-job rule when someone applied to both, re-labels the job, and shows it as new.
- **Matching:** same company + normalised title + location (`jobs.repost_key`), then a near-identical description, checked by the pipeline. Two separate hiring batches with different text stay two jobs.
- **Schema:** `db/postgres/0002_job_aliases.sql`. The detection code comes with the pipeline's move to Supabase.

---

## 2026-10-16 — How schema changes reach Supabase (M3)
- **Options:**
  - paste each `db/postgres/*.sql` file into Supabase's SQL Editor by hand
  - a GitHub workflow applies new files automatically
- **Choice (Shrey):** the workflow (`.github/workflows/supabase-migrate.yml`, running `scripts/apply_pg_migrations.sh`).
- **Why:** repeatable and logged, like the D1 migrations; no file gets forgotten. The data migration runs from GitHub Actions too, with the same `SUPABASE_DB_URL` secret.
- **How it works:** runs on pushes to main that touch `db/postgres/`, or by hand. Each new file runs in one transaction with its row in `schema_migrations`, so a failing file leaves nothing half-applied and is retried next time. Files are never edited after they're applied; changes go in a new numbered file.

---

## 2026-10-15 — Where FastAPI runs with Supabase (M3)
- **Options:**
  - stay on Cloudflare Python Workers and reach Supabase Postgres through Hyperdrive
  - Render free web service
  - Google Cloud Run
- **Choice (Shrey):** Cloudflare Python Workers + Hyperdrive.
- **Why:** nothing moves (same deploy, same URL), and it never sleeps, so there's no cold start for students on slow phones. Render sleeps after 15 min idle (about a minute to wake); Cloud Run needs a card on file.
- **Free tier (checked 2026-10-15):** Workers 100k requests/day and 10 ms CPU per request; Hyperdrive 100k database queries/day. Python Workers gained Hyperdrive support in Sept 2026, so examples are few.
- **Ruled out:** Fly.io and Railway (no free tier for new accounts), Koyeb (card hold, one service, Frankfurt/Washington only).
- **Consequences:**
  - The D1 binding is replaced by a Hyperdrive binding with a Postgres driver; the queries move from SQLite to Postgres syntax.
  - Long-running work (the referral agent, Phase 3+) won't fit 10 ms of CPU and will need its own host then.

---

## 2026-10-15 — Multi-user schema (M2 done)
- **Designed by Shrey** over four revisions; Claude reviewed with stress tests. Full table list in `docs/plan.md` §12.
- **Options for job labels** (level, yoe, evidence):
  - columns on the `jobs` row (today's D1 layout)
  - a separate `job_labels` table
- **Choice (Shrey):**
  - Six tables: `universities`, `students`, `companies`, `jobs`, `applications`, `job_labels`.
  - Things that exist on their own (universities, students, companies, jobs) each get an `id`.
  - Events between them (a student applying to a job) live in `applications`.
  - Labels live in `job_labels`, tagged with `rules_version`.
- **Why:**
  - One student applies to many jobs, so application status belongs to the application, not the student.
  - University and company names are stored once, so "Lucknow University" vs "University of Lucknow" can't split a group, and one URL change edits one row.
  - The posting (written by the company, changes rarely) and the labels (written by our rules, change on every rules update) are kept apart. A re-label never touches `first_seen_at` or the description, and old vs new labels can be compared to check fresher precision didn't regress.
- **Rules against duplicates (Shrey):**
  - one `applications` row per (student, job)
  - one `companies` row per company, one `universities` row per university
  - a new `job_labels` row only when the label actually changes
  - keep only the current and previous label per job, to stay inside the 500 MB free tier
- **Trade-off:** the job list needs one extra join to read the current label.

---

## 2026-10-15 — Database and login (M1, part 2; M1 done)
- **Options:**
  - Supabase Postgres + Supabase Auth
  - Neon Postgres + Better Auth
  - stay on Cloudflare D1 (SQLite) and add a login provider
- **Choice (Shrey):** Supabase Postgres + Supabase Auth.
- **Why:**
  - Postgres replaces SQLite once there are users. It gives row-level security (each student reads only their own rows, enforced by the database), full-text search, and pgvector for skill↔job matching and the referral agent.
  - Supabase Auth gives email magic links plus Google and LinkedIn sign-in ("Sign in with LinkedIn" = OpenID Connect profile/email only; see `docs/plan.md` §10).
  - Supabase Storage holds resumes later.
- **Free tier (checked on supabase.com/pricing, 2026-10-15):**
  - 500 MB database
  - 1 GB file storage
  - 50,000 monthly active users
  - 5 GB egress
  - 2 active projects
  - no backups
  - paused after 1 week without activity
- **Pro ($25/mo):** 8 GB database, 100k MAU, daily backups, no pausing. Budget decision: later (Shrey), so we stay on Free until launch.
- **Watch the 500 MB:** ~21k jobs with full descriptions (~5 KB each) and evidence is already ~150 MB.
  - Closed jobs should drop their description after a while (M2/M3 design).
  - The pipeline keeps writing only changed rows.
- **Consequences:**
  - The database and FastAPI move off Cloudflare D1 / Python Workers. The container host is picked in M3 (data migration), where the free options (Render, Railway, Fly) are compared then.
  - The pipeline (GitHub Actions) writes to Postgres instead of D1.
  - Cloudflare stays for the domain and CDN.

## 2026-10-15 — Backend, frontend, platform order (M1, part 1)
- **Backend. Options:** FastAPI · Django (built-in admin, auth and ORM; the API would be rewritten) · TypeScript (Next.js API routes / Hono)
- **Choice (Shrey):** FastAPI. It's already built, async and streaming-friendly for AI agents, and shares Python with the pipeline. Where it's hosted is decided together with the database.
- **Frontend. Options:** Next.js · React + Vite (current)
- **Choice (Claude, delegated by Shrey):** Next.js (React + TypeScript, App Router).
  - Server-rendered job pages get indexed and show preview cards on WhatsApp and LinkedIn, which is the main growth channel across colleges.
  - The motion and graphics libraries (Motion, GSAP, React Three Fiber, Rive) all work, as client components.
  - The migration from Vite happens in M4.
- **Platforms (Shrey):** web first; a mobile app later. Shared TypeScript types, API client and design tokens keep a React Native/Expo app cheap to add.
- **Frontend quality (Shrey):** no "AI slop". `CLAUDE.md` now has a "Frontend standards" section: banned patterns, design tokens first, the motion/graphics toolkit, motion rules, a performance budget and a process.
- **Still open in M1:** the database and login (options in this conversation: Supabase Postgres + Supabase Auth, Neon + Better Auth, or staying on Cloudflare D1).

## 2026-10-08 — More hiring sources: company career sites
- **Options:** a career-page reader (schema.org job data, SuccessFactors, Oracle Recruiting) · GitHub new-grad lists · Adzuna India API · public Google Sheets lists · Reddit/Telegram. Ruled out: X/Twitter (reading needs the paid API; scraping breaks its terms), and Wellfound, Naukri, Instahyre, Cutshort, YC Work at a Startup (no public API; terms forbid scraping).
- **Choice (Shrey):** the career-page reader first.
  - `sources/careersite.py`: the sitemap lists job pages. URL words are screened for India and for titles the role rules could accept, then each page's schema.org JobPosting (JSON-LD or SuccessFactors microdata) is read. Their RSS feeds under `/services/` are robots-disallowed, so they aren't used.
  - `sources/oracle.py`: the JSON API Oracle Recruiting career sites call themselves.
  - Both fetch at most 150 job pages per board per run (newest first) and reuse stored pages for 3 days.
- **Added (all `india_only`):** EY, Capgemini, HCLTech, Wipro, ZS (careersite); KPMG India, KPMG Global Services, EXL (oracle). ZS's robots.txt asks for a 5 s crawl delay, which the per-host pacing honours. HCLTech and ZS URLs don't name a place, so those pages are fetched and their location checked after the India ones.
- **Checked, not readable:**
  - Globant: no job data on its pages.
  - EPAM: gzipped sitemap and `/vacancy/` paths; 0 India roles anyway.
  - Persistent: its sitemap lists only the homepage.
  - Infosys: blocked by Akamai.
  - Flipkart: uses TurboHire.
  - Urban Company, Zerodha, Swiggy: JavaScript-only sites.
  - IBM, Deloitte: on Avature, with empty or other-host sitemaps.
- **Future scope (Shrey):** a "Paste a job link" box, admin only, for jobs seen on X, WhatsApp or Telegram. Not built.

## 2026-10-08 — Every job on the page; Gemini only on request
- **Why:** a run found 37 target freshers, but the page showed 4. The location rules and the 30-day age rule hid the rest before the reader chose anything.
- **Scope. Options:** every job with every filter · target roles at every location · today's role and location rules at every level
- **Choice (Shrey):** every open job (~21k), newest first, 20 per page with page numbers.
  - Experience filter: all, fresher, internships (by title), 0–1 to 0–5 yrs, not stated, experienced.
  - Role filter: all, my target roles, AI/ML, backend, mobile.
  - Posted filter: any, new in 24h, 7 days, 30 days. This supersedes "hide postings older than 30 days".
  - The location and visa rules become an opt-in "Only where I can work" filter.
  - The rules still label every job; nothing about what counts as fresher changes.
- **Pipeline LLM:** removed (Shrey). The 2026-10-07 Gemini review of `maybe` jobs is gone; labels come from the rules only.
- **Gemini fit check:** built, but off (Shrey: "build it as a feature, don't enable it for now"; who may use it is decided later).
  - `POST /api/jobs/{id}/fit` compares a resume the reader pastes (kept in their browser, never stored) with one job.
  - It runs only when the Worker has `FIT_CHECK = "on"` and a `GEMINI_API_KEY` secret. Until then it answers 404 and the button is hidden.
  - Each check is one free-tier Gemini request.
- **Free-tier reads (D1, 5M rows/day):**
  - Migration 0005 replaces `idx_jobs_feed` with `idx_jobs_recent` and `idx_jobs_level`, both ending in the sort key, so a page reads about 20 rows.
  - The total is counted only once per filter set.
  - The filter lists come from a snapshot that publish writes after each run (one row), instead of ~100k reads per page load.
  - Rare filters (country, search) still scan more. Building the index writes about one row per job once, in the next run.
- **Write cost:** each insert now touches two indexes, so `COST_INDEXED` is 3. That's still under 100k rows/day at 8 runs.

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
