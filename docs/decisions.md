# Architecture decisions

Newest first. Each entry: date, options considered, choice, why.

---

## 2026-11-11 — Worldwide coverage: every country, all jobs
- **Options:** every country, all jobs · companies from everywhere but only jobs open to India ·
  a few regions first
- **Choice (Shrey):** every country, all jobs. Reverses point 3 of the 2026-10-18 coverage
  strategy (keep only India, remote and visa/relocation jobs from global companies).
- **Why:** Aventra is for every job seeker, not only people in India.
- **Consequence:** the 500 MB database is the first limit (about 190 MB used with the India
  filter on). The plan and six open choices (storage first) are in
  `docs/strategy/worldwide-coverage.md`. Nothing is built until Shrey picks.

## 2026-11-12 — India first: 237 companies added for checking
- **Asked of Shrey:** which kinds (YC startups in India · funded startups and unicorns · the 54
  listed but unread · IT services), how many (about 50 · 200 · 500), and which roles (tech for
  now · all roles now). **Choice:** all four kinds, about 200, tech roles for now.
- **Added to `config/companies.yaml`, all unverified:**
  - 103 India-based YC companies of any sector with a website and 10+ people, from the yc-oss
    dataset (`scripts/import_yc.py --india`; the AI-only filter had kept 14).
  - 107 Indian startups and scale-ups, drafted by Claude from memory with their websites, for
    Shrey to prune. A wrong website costs nothing but a failed check.
  - 27 IT services and consultancies, marked `india_only` because their boards are large.
- **How they become jobs:** nothing is fetched from an unverified company. The verify workflow
  probes Greenhouse, Lever, Ashby, Workable and SmartRecruiters by name on this PR; the weekly
  careers detector reads each website for any other system. From earlier runs, expect roughly a
  quarter to a third to verify; the rest are on systems we don't read or sites that render in
  the browser.
- **The 54 listed but unread: not fixed.** The detector's last run found no readable system for
  most (Flipkart, Zepto, Ola, Dream11, Myntra: "not found"; Haptik: Freshteam; Chargebee:
  LinkedIn only; Rapido: Darwinbox, which refuses GitHub's runners). This sandbox can't reach
  their sites, so the next step is a workflow that saves sample pages for the commonest unread
  systems (Freshteam first), to build adapters from real fixtures.
- **IT services:** TCS, Infosys and similar hire freshers through their own portals, some
  behind a login. Listed so the detector can try; any that need a login stay unread.

## 2026-11-12 — Closed jobs are deleted after 14 days (built)
- **Decided 2026-11-11 (Shrey); built now** because the measurement put it first: 15,990 of
  39,631 stored jobs were closed.
- **How:** a new `jobs.closed_at` (`db/postgres/0009_closed_at.sql`), set when a job closes and
  cleared when it reopens. Each publish deletes jobs closed 14 days or more, with their labels
  (cascade) and their text in Storage.
- **Never deleted:** a job someone saved, applied to, checked their fit against or tailored a
  resume for. Those rows cascade from `jobs`, so deleting the job would take the person's
  history with it.
- **Existing closed jobs. Options:** count them as closed today (all go in 14 days) · count them
  as closed 14 days ago (all go on the next run). **Choice:** closed today. Some closed
  yesterday; a job deleted and then re-listed would come back as "New" with a fresh first-seen
  date, which the 14 days exist to prevent. Cost: the space comes back around 2026-11-26.
- **What Insights keeps:** `runs` still records jobs opened and closed per run, so trends
  survive the rows.
- **Note:** Postgres reuses the freed space for new rows; the database's size on disk doesn't
  shrink by itself. "Measure storage" before and after shows the effect on what fits.

## 2026-11-12 — Measured: Postgres holds about 99,000 jobs, not 400,000
- **Measured (Shrey's run of "Measure storage"):** 241.5 MB of 500 MB used; 39,631 jobs stored
  (23,641 open, 15,990 closed); description text is 60.4 MB; everything else is 4,480 bytes a job.
- **What it changes:** moving text to Storage frees a quarter of the database, not most of it.
  The estimate of 400,000 to 500,000 jobs in the plan was wrong by about four times. The rows,
  labels and indexes are the limit now.
- **Next, in order:** the 14-day shelf life for closed jobs (decided 2026-11-11; 40% of stored
  jobs are closed), then one label version a job and slimmer evidence, each measured before and
  after. Options and costs are in `docs/strategy/worldwide-coverage.md`, Part 2. India plus
  Europe still fits; "every country, every role" does not fit the free tier at once.

## 2026-11-12 — Hacker News: a person's own profile is not a job
- **Bug (reported by Shrey):** people post their own profile in the "Who is hiring?" thread in
  the same "Name | Role | Place" shape as a company, and it was listed as a job.
- **Fix:** `sources/hn.py` skips a post that uses the job-seekers' template ("Willing to
  relocate:", "Résumé/CV:") or describes its author in the first person with nothing an employer
  would say (we, our, hiring, apply, "looking for a backend engineer"). A founder writing "I'm
  the CTO, we're hiring" is kept. Fixtures first, in `tests/test_hn_source.py`.
- **Limit:** not tried on the live thread (this sandbox can't reach HN). A real post it drops by
  mistake is a missed job, which the precision rule accepts. Profiles already stored close by
  themselves after two pipeline runs, since the source no longer returns them.

## 2026-11-12 — The four-section layout, built, with motion
- **Built from** `docs/wireframes/app-v2.html` (approved 2026-11-11). A route group `(app)` holds
  the frame: a sidebar on wide screens, a tab bar on phones, and a search bar at the foot of
  every page that opens the command palette. Each page has a top bar with its own controls, the
  theme switch and the profile button.
- **Jobs:** filter chips on top, with years back as the first chip ("I have 3 years", filled
  marigold when set); a flat list, newest first; the job on the right. The years headline and
  the filter rail built on 2026-11-11 are removed, as the approved sketch has neither.
- **Applications** (`/applications`, new): filter bar (needs me, stage, company, with a tailored
  resume, search), then a board or a list. Built for hundreds: a column shows six cards and
  "Show more"; applications with no reply in 30 days and the Closed column fold into a stack;
  past 40 applications the list opens by default, 20 a page, what needs the person first. A
  marigold tape on a card means it needs them this week. The next step on each card is a rule
  over stage and dates (`lib/board.ts`), never a guess. `/profile` still receives sign-in links
  and forwards here.
- **Insights:** the market merged in. What companies ask for against the resume, and how much of
  the market is open at the person's years (from the snapshot's `within_years`), above their
  own week. **Not there, because the pipeline doesn't compute them yet:** change over 30 days,
  jobs per week, days open, who is hiring most, pay.
- **Agent** (`/agent`, new). **Options for the parts with no backend (chat, outreach, applying):**
  show only what is real · hide the tab · show them marked as coming. **Choice (Shrey):** only
  what is real. The page holds today's strong matches, follow-ups, tailored resumes, fit checks
  and the daily allowance.
- **Not built from the sketch:** the calendar view, grouping several jobs at one company into
  one card, and a server-side page of applications (the tracker still loads them in one request).
- **Motion, each with a reason:** the sidebar marker and the view switch slide to the choice;
  a pressed control gives slightly; a page, and a newly chosen job, rise 8 px into place; on
  phones a job rises as a sheet; counts tick when they change; a card settles into the column
  it was moved to; the bookmark pops once on save; menus and the palette grow from their corner;
  chart bars grow from the baseline; the highlighter and ruler from 2026-11-11 stay. CSS only,
  transform and opacity only, all off under reduced motion.
- **Budget:** the job list downloads 154.7 KB of JavaScript gzipped (limit 170).
- **Checked:** lint, types, token sync, static build; screenshots of all four sections at 1360 px,
  Jobs and Applications at 390 px, Jobs in dark, the tracker at 118 applications as a list, with
  sample data and a stand-in sign-in. **Not checked:** against the live API and a real account,
  drag and drop by hand, the board at 118 applications, keyboard navigation, a real phone,
  throttled-4G timings.

## 2026-11-12 — Job text goes to Supabase Storage, not R2
- **Why revisit:** Cloudflare needs a payment card to switch R2 on and accepted neither Shrey's
  RuPay card nor PayPal.
- **Options:** Supabase Storage (already used for resumes, no card, 1 GB free) · Cloudflare D1
  (no card, 5 GB free but 500 MB a database, so text would be split across databases) · leave
  the text in Postgres (~70k jobs, enough for India but not Europe).
- **Choice (Shrey):** Supabase Storage.
- **How it differs from the R2 build of 2026-11-11:** a public `job-text` bucket made by a
  migration; the pipeline writes over Storage's REST API with the project's secret key (one new
  GitHub secret, `SUPABASE_SECRET_KEY`; boto3 is gone again); the API reads the object's public
  URL, with the jobs table as the fallback, and only when the repo variable `JOB_TEXT` is `on`.
  The dual-write order, the rollback on a failed upload, the backfill with its verify step and
  the measuring script are unchanged. Steps for Shrey: `docs/setup-job-text.md`.
- **Costs against R2:** 1 GB instead of 10 GB (about 400k descriptions as plain text; compressing
  them would triple that when needed); the read leaves Cloudflare's network for Supabase's
  region, so opening a job is likely slower than it would have been with R2; Storage pauses with
  the database after a week without activity, which the 3-hourly pipeline prevents.
- **Measured (Shrey's run of "Measure storage", 2026-11-12):** 23,641 open jobs and 39,631 stored
  in all across 13 careers systems; descriptions average 1.0 to 2.8 KB by system, about 2.3 KB
  for the three largest. The table and index sizes from the same run are still to be added to
  `docs/strategy/worldwide-coverage.md`.

## 2026-11-11 — Moving job text to R2: how (phase 1, first half)
- **Order. Options:** cut over in one change (drop the column, read only R2) · write to both,
  copy the old rows, read R2 with Postgres as the fallback, drop the column later.
  **Choice:** both, then cut over, the same shape as the D1 to Supabase move (2026-10-16). At
  every step Postgres still has the text, so undoing it is removing two secrets.
- **Built:** `scripts/text_store.py` (R2 over its S3 API with boto3, a new pipeline-only
  dependency), `publish_pg.py` uploads each new or changed job's text before its transaction
  commits (a failed upload rolls the run back; the next run retries), `scripts/backfill_r2.py`
  with a verify step, `api/src/job_text.py` reading through the Worker's R2 binding, and
  `scripts/measure_storage.py`. Objects are plain UTF-8 text under `text/<sha256 of job id>`.
- **Off until set up:** with no R2 secrets the pipeline writes Postgres only, and the Worker's
  binding is commented out in `wrangler.jsonc` because a deploy fails when its bucket is
  missing. Steps for Shrey: `docs/setup-r2.md`.
- **Free tier (checked 2026-11-11):** 10 GB, 1M writes and 10M reads a month. Cloudflare asks
  for a payment card to switch R2 on; usage inside the limits is not billed. **For Shrey to
  confirm** against the free-tools rule before step 2 of the setup.
- **Found on the way, to do before the column can go:** the job list reads pay from the first
  line of the description, and repost matching compares full texts from Postgres. Pay needs its
  own column and reposts a stored fingerprint.

## 2026-11-11 — Worldwide coverage: storage, order and languages
- **Storage. Options:** everything in Postgres (~70k jobs) · slim rows in Postgres with
  descriptions in Cloudflare R2 and closed jobs deleted after 14 days · the same, keeping closed
  jobs. **Choice (Shrey):** slim rows + R2, 14-day shelf life. Free tier: R2 10 GB, 1M writes and
  10M reads a month. Cost: search covers title and company, not full text; Insights keeps weekly
  totals instead of old rows.
- **At the free ceiling. Options:** region by region · biggest employers first · tech and data
  companies first. **Choice (Shrey):** region by region.
- **First regions (Shrey):** India and Europe.
- **Languages. Options:** English first, others "Not stated" · rules before a region launches ·
  hide other languages. **Choice (Shrey):** English first.

## 2026-11-11 — All roles, matched per person at request time
- **Options:** tech and data roles only (a quarter of the volume) · every role
- **Choice (Shrey):** fetch every job, every role, and let each person filter by their own
  preferences.
- **Consequence:** the pipeline stops matching jobs against `config/profile.yaml`. It labels
  every job with profile-independent facts (a job family from a fixed list, years, places,
  workplace, visa, skills) and the API filters by the signed-in person's preferences.
  `role_match` goes; the title screen and the India screen go. Free storage then holds a few
  hundred thousand open jobs, so the order companies are added in becomes a product decision.
  Plan and open choices: `docs/strategy/worldwide-coverage.md` (rewritten today).

## 2026-11-11 — App layout approved (Shrey)
- **Approved:** the four-section sketch in `docs/wireframes/app-v2.html`, with three changes
  Shrey asked for, now in the sketch: a profile button at the top right of every page; a filter
  bar above the Applications board; the Jobs list is flat, newest first, without the
  grouped-by-fit sections.
- **Next:** build in the order shell and Jobs, Applications, Insights, Agent. The agent's open
  questions below still stand.

## 2026-11-11 — The app's four sections, and the layout for them (sketch stage)
- **Sections (Shrey):** Jobs · Applications (track every job applied to) · Insights, with the
  market merged in (what companies ask for against the person's profile, how to close each gap,
  market sentiment) · Agent (talk to it, have it prepare applications and outreach, improve the
  resume, and keep every tailored resume).
- **Layout (Shrey liked ideas 1 and 3 of `docs/wireframes/ideas.html`):** Workbench's sidebar,
  dense grouped rows and command bar, with Pinboard's paper notes for boards, big serif numbers
  and view switches. The command bar on every page is the agent's input. Sketches:
  `docs/wireframes/app-v2.html` (`?s=jobs|apps|insights|agent|resumes`), screenshots `v2-*.png`.
- **Kept from 2026-10-19:** nothing goes out under a person's name without them reading it. In the
  sketch the agent drafts notes and fills forms; the person sends and submits.
- **Open, for Shrey:** whether the agent may ever submit an application itself; which model runs
  the chat and where long agent work runs (Workers allow 10 ms CPU per request); the new market
  numbers the pipeline must compute (skill share and its change, jobs per week, days open, pay).

## 2026-11-11 — App redesign: the three directions mixed (job list built)
- **Scope options:** app pages only · landing and app, fresh identity · landing only
- **Choice (Shrey):** app pages move to the landing page's identity; the landing page stays.
  Claude builds, Shrey reviews.
- **Direction (Shrey, after seeing `docs/wireframes/next.html`):** mix all three, because Ledger
  alone had no visible filters.
  - From **Ledger:** paper and warm ink, Instrument Serif headings, and the highlighter over the
    words in the quoted line that decided the label (it sweeps in once when a job opens).
  - From **Console:** every filter open in a rail beside the list with live counts (chips stay on
    phones), the ruler (bar = what the job asks, tick = your years) in each row and in the
    evidence card, and the graphite dark theme.
  - From **Billboard:** years of experience as the page's headline control ("I have 3 years of
    experience"), replacing the "Asks" chip.
- **Tokens:** the app's white and purple are replaced by the landing's paper, ink and marigold in
  `globals.css` and `tokens.ts`. Marigold is a fill only; new `accent-text` (blue on paper, amber
  on graphite) is the text version, and `mark` is the highlighter. Every text pair is 4.5:1 or
  more (computed; figures in `globals.css`).
- **Type:** Instrument Serif (headings, years), Instrument Sans (text, replaces Geist) and Geist
  Mono (data), loaded once in the root layout. Three families against CLAUDE.md's two, the same
  exception the landing page already has; say if the mono should go.
- **Budget:** the job list downloads 153 KB of JavaScript gzipped (limit 170), no new libraries.
- **Checked:** lint, types, token sync, static build; screenshots at 390 and 1280 px, light and
  dark, with sample jobs in place of the API (this sandbox can't reach it). **Not checked:** the
  signed-in pages (board, insights, profile) on screen, a real phone, throttled-4G timings.

## 2026-11-04 — Job list polish and the pipeline-first dashboard
- **Brief (Shrey):** on the job list, real logos or per-company tints, a sticky action bar,
  visibly active filter chips with "Clear all", a requirements card without dead space and with
  semantic colours. The dashboard becomes a command center: a one-sentence brief with one
  action, a kanban tracker with drag and drop, a Today rail (strong matches, follow-ups, the
  fit-check ring, the top missing skills), an Insights page (timeline, applications per week
  against a goal), header nav (Jobs, Board, Insights) and a Cmd+K palette. B.4 is on hold.
- **Logos. Options:** a free favicon service by domain with a tinted-letter fallback · logos
  fetched once by the pipeline and self-hosted · tinted letters only. **Choice (Shrey):** favicon
  service (DuckDuckGo's icon endpoint) plus tint fallback. The service sees which company domains
  a visitor's browser asks for. Only 57 of 433 working companies had a known website, so a
  backfill adds domains, keeping a guess only when that site's title names the company.
- **Strong match. Options:** rules (new in 24 hours, fits years and roles, and the resume has at
  least half of the skills the posting names) · only Gemini-checked "strong". **Choice (Shrey):**
  rules; a Gemini verdict upgrades a card once checked.
- **Weekly goal (Shrey):** a goal on the profile, default 5 (adds `students.weekly_goal`). A job
  sitting in Applied for 7 or more days is "follow-up due".
- **Pages (Shrey):** Jobs `/` (the list), Board `/profile` (the command center), Insights
  `/insights` (timeline, weekly chart, full skill gap).

## 2026-11-04 — Part B.3: the tailored resume
- **Promise:** reword and reorder the saved resume toward one job, never adding a skill, a number
  or a claim; show a diff; download a PDF.
- **LLM. Options:** Gemini Flash-Lite free tier (already wired: key, quota, failure handling;
  Google may use what is sent) · Groq Llama 3.3 70B free tier (no training on data, but a new
  provider and key). **Choice (Shrey):** Gemini, with the same privacy note as the fit check.
- **Guard:** whatever the model writes, a rules check compares each rewritten line with the
  resume lines it cites; a line naming a catalogued skill or a number its sources don't have is
  dropped back to the original wording.
- **Download. Options:** a clean one-page PDF in our own template, made in the browser (library
  loaded only on that page) · the original PDF's layout, edited (fragile) · a .docx.
  **Choice (Shrey):** our own PDF template.
- **Limit (Shrey):** its own count, 2 tailored resumes per person in any 24 hours, separate from
  the 5 fit checks.

## 2026-11-04 — Job list JS budget: what was over, and how it is measured
- **Finding:** summing every chunk named in `out/index.html` gave 193.8 KB gzip, but 39.5 KB of
  that is Next's `noModule` polyfill script, which no browser that runs ES modules downloads. A
  Playwright load of `/` showed what browsers really fetched: **228 KB**, because `next/link`
  prefetched `/login` and `/profile` as soon as "Sign in" was on screen, pulling in supabase-js
  (56 KB) and the login chunk on every visit.
- **Change:** the job list's links (`ProfileButton`, `SavedNote`, `JobActions`) use
  `IntentLink`, which prefetches on hover, focus or touch instead of on entering the viewport.
  Real download on `/` is now **154 KB** gzip (React DOM 72 KB + Next runtime ~62 KB +
  app code ~19 KB). Screens are unchanged.
- **Tradeoff:** a first tap on "Sign in" or "Profile" on a phone starts the fetch at touch
  rather than earlier, so that one navigation can be slightly slower on 4G.
- **Measurement (proposed, Shrey to confirm):** count the scripts a modern browser loads for
  the route, i.e. skip `noModule` scripts. The old sum cannot reach 170 KB: framework chunks
  plus the polyfill are already ~176 KB with zero app code.

## 2026-11-04 — Fit-check cap and the profile dashboard
- **Fit check. Options:** A rules only (free, instant, every job, shallow) · B Gemini only, one
  job at a time · C both. **Choice (Shrey):** B, Gemini only, at most 5 checks per person per day,
  with a notice before the first check that Gemini's free tier may use what it is sent. The
  server counts checks and keeps each verdict (`fit_checks`), so the cap holds and the dashboard
  can list recent verdicts. The dashboard's other boxes are counting rules, never Gemini.
- **Profile button (Shrey):** top right on every page: "Sign in" when signed out; the person's
  initial when signed in, opening Profile and Sign out. The job list checks the stored session
  itself, so supabase-js stays off it.
- **Skills (built for box 2):** the pipeline now reads each posting's full text for the skills
  in `config/skills.yaml` (rules, `extract/skills.py`) and stores them in `job_labels.skills`. A
  hit is the skill's own word, so no separate snippet is stored. The browser checks the saved
  resume against the same catalogue (`site/src/lib/skills.json`, exported from the YAML).
  EXTRACT_VERSION 5 re-labels every open job once on the next run.
- **How the API knows who is asking (built):** the site sends the Supabase access token, and the
  API asks Supabase's `/auth/v1/user` whether it is valid (one small request; no signing keys or
  crypto in the Worker). The check reads the saved resume itself, so nothing is pasted. A check
  holds its place while Gemini answers and is removed if Gemini fails, so failures don't count;
  checks sent at once are counted one after another (a row lock). "A day" is any 24 hours.
- **Dashboard (Shrey), first version:** (1) jobs for you, with new in the last 3 days (Shrey: no "last visit" column for now);
  (2) resume vs. the market, the skills most asked for in jobs that fit you, ticked when the
  resume has them; (3) your details, the current form; (4) a tracker, Saved → Applied →
  Interview → Offer / Rejected, with a Save button on each job (applications gains a `saved`
  status); (5) fit checks left today and recent verdicts. Layout as sketched: jobs for you and
  fit checks on top, then the tracker, then resume vs. the market; details on their own page. Tailored resumes (B.3) and outreach (B.5) appear only once built.

## 2026-11-04 — After saving a profile, go to the jobs it fits
- **Found (Shrey):** saving showed "Saved." and nothing else, so a person didn't know what to do next.
- **Options:** a panel with a "See your jobs" button, staying on the form · go straight to the
  job list, filtered by the profile, with a one-time "Profile saved" note · a toast plus a
  "Your jobs" link in the header.
- **Choice (Shrey):** straight to the job list. The filters come from the profile: its years
  ("3+" becomes "≤ 3", precision first) and its role when exactly one is picked, otherwise all
  three target roles. The note says what the list shows and links back to "Edit profile".

## 2026-11-03 — Rename to Aventra; a new address now, our own domain later
- **Name (Shrey):** the product is **Aventra**, its only name. Replaces Kario everywhere a
  person or a fetched server sees it: the wordmark and the "a" mark (regenerated from Instrument
  Serif by `brand/make_logo.py`), page titles, copy, the Worker, the API title, the User-Agent
  and browser storage keys (saved theme choices reset once). The GitHub repo keeps the name
  `frshmen`; older entries below keep the name they were written with.
- **Address. Options:** our own domain (the one being bought for Resend; the workers.dev link
  could keep working) · rename on workers.dev (free and immediate, but the old link breaks) ·
  both, workers.dev now and the domain at launch. **Choice (Shrey):** both. The Worker becomes
  `aventra` and the Cloudflare account subdomain `getaventra`, so the site moves to
  `https://aventra.getaventra.workers.dev`. Google and Supabase settings get the new address
  now, and are updated once more when the domain arrives.
- **Caution raised:** "Aventra" may already be used by a Finnish identity company (Aventra Oy).
  Shrey to check the domain and the IP India and EUIPO trademark registers before launch.

## 2026-10-30 — Part B.1: sign-in and resume storage
- **Sign-in. Options:** Google only (one button, no email deliverability work; Google OAuth is
  needed anyway for the `gmail.compose` drafts in B.5) · Google plus an email magic link (covers
  people without a Google account or on a work address).
- **Choice (Shrey):** Google plus an email link. Limit to note: Supabase's built-in mailer sends
  about 2 auth emails an hour on the free tier, so email sign-in needs a free SMTP sender before
  launch (decided separately).
- **Resume storage. Options:** PDF in Supabase Storage plus the extracted text in Postgres · text
  only (nothing private in a file bucket, but B.3 would rebuild the layout from plain text and
  users can't re-download their original).
- **Choice (Shrey):** PDF plus extracted text. The PDF sits in a private Storage bucket, one folder
  per user, guarded by row-level security; the text goes in Postgres for the fit check and the
  tailored resume. Free tier: 1 GB Storage, 50 MB per file.
- **Auth client. Options:** supabase-js, loaded only on the sign-in and profile pages (about
  45 KB gzip; handles PKCE, token refresh and Storage uploads; the mobile app can reuse it) ·
  our own PKCE and refresh code against Supabase's REST API (about 3 KB, but we'd own the edge
  cases). **Choice (Shrey):** supabase-js, lazy-loaded. The job list's 170 KB budget is untouched.
- **Resume text. Options:** pdf.js in the browser on the profile page (instant, and the user can
  check the text before saving) · a GitHub Actions job running pypdf on new uploads (no extra JS,
  but minutes late). The Worker's 10 ms CPU limit rules out parsing there. **Choice (Shrey):** in
  the browser, pdf.js lazy-loaded on the profile page only.
- **Email sender. Options:** decide at launch (Supabase's mailer meanwhile) · Brevo free (300 a
  day, single verified sender, no domain, but likely spam-foldered) · Resend (free: 3,000 a month,
  100 a day) on our own domain. **Choice (Shrey):** Resend with a domain. The domain is the
  project's first paid item (about $10 a year), an explicit exception to "free tools only".
  Until it exists, email links go through Supabase's mailer (about 2 an hour), enough for testing.
- **Profile data path. Options:** the browser reads and writes its own profile row and resume
  file in Supabase directly, guarded by RLS (no Worker requests or CPU; supabase-js already does
  it) · everything through the FastAPI Worker (one door, but Worker CPU and a token check on every
  call). **Choice (Shrey):** directly, with RLS. Condition he set: the RLS tests are
  non-negotiable. `tests/test_rls.py` runs as Supabase's `anon` and `authenticated` roles with
  Supabase's default grants, and must prove that nobody can read or change another person's
  profile or resume, and that every public table has RLS on.
- **Profile fields (Shrey):** name, years of experience, graduation year, target roles, resume.
- **D1 backup:** Shrey chose to keep it for now (it costs nothing); ask again before deleting.

## 2026-10-23 — Landing v2: the critique roadmap, for every job seeker
- **Context:** two design critiques of `/preview` (the second unconstrained, benchmarked against
  current award sites) scored it about 5.5/10: clean, honest, but every visual borrowed. Shrey:
  "do all of them in order", and the page is for **everyone looking for a job, not only 2026
  graduates**.
- **Constraints Shrey set for the landing page:** treat every feature it shows as built (they
  ship before launch); the audience is on good laptops, so the landing page is no longer held to
  CLAUDE.md's budget-phone limits (the 170 KB budget still applies to the job list); the only hard
  limit is money (free tools and fonts).
- **Roadmap, one commit each:** fix the critique's bugs; the Highlighter hero (a WebGL wall of
  real deciding lines, `/api/evidence`); How it works as a pinned sideways track whose cards act
  out each step; Ink and Marigold with serif and sans type; copy rewritten around the reader's
  years; a shader globe that dives into India; the micro layer; a departure-board data band.
- **Palette "Ink and Marigold"** (replaces navy, parchment and cobalt from earlier today): paper
  #F2EEE4 / #E9E3D6 / #FBF9F4, warm ink #121110, graphite chapters #14130F, one marigold
  highlighter #FFB21A as the action colour and the evidence mark, strike #B5381F, pass #3FA66A,
  links #1F4FD8. Why: the brand is evidence, so the page is paper and ink with a highlighter, and
  navy plus blue-600 was Tailwind's defaults.
- **Type:** Instrument Serif for headings (the wordmark is drawn from it), Instrument Sans for
  text, Geist Mono for evidence and data. Fontshare's Satoshi and Switzer were the critique's
  first pick for text, but Fontshare is unreachable from here; Instrument Sans pairs with the
  serif and is on Google Fonts.

## 2026-10-23 — Landing palette: midnight navy, warm parchment, Klein cobalt
- **Choice (Shrey):** "high-authority enterprise and fintech". Navy chapters #080D1A with #0F172A
  elevated (hero, globe, footer, terminal blocks); parchment chapters #FAF8F5 with #EFECE6 bento
  cards and #FFFFFF inner surfaces (sources, How it works); Klein cobalt #2563EB as the one action
  colour (white text on it, 5.2:1; #60A5FA where cobalt is text or a marker on navy); #059669 as
  the pass signal. Replaces carbon, limestone and light orange from earlier today.
- **Also:** the globe's "Live" status bar and the hero's "356 fresher roles open now" badge are
  gone (the count stays on the top bar's button). The top bar is clearer white glass, and its text
  follows what is underneath: light over navy, dark over parchment.

## 2026-10-23 — Landing craft pass: limestone and pine, machined glass, windowed cards
- **Choice (Shrey):** the white chapters become warm limestone (#F6F5F0 page, #ECEAE2 stone frames
  with #DDD9CE borders, #FFFFFF windows); terminal blocks and dark buttons are deep pine (#0B1612);
  emerald-500 marks matched or verified and amber-600 marks missing. Carbon stays for the hero,
  globe and footer, light orange stays the one action colour. New `--lp-*` roles: window-bar,
  window-line, ok, warn, warn-text, term, term-ink, term-muted, term-ok.
- **Machined glass** (`.machined-glass` in `landing.css`): 135° sheen, 24px blur with 180%
  saturation, layered specular edges. On the top bar (over an 88% carbon body so it stays legible
  on limestone), the globe's status bar and the city counters. Corner reticle ticks frame the globe.
  There is no separate hero panel, so these are the panels it went on.
- **How it works cards** are application windows (stone frame, white window, 36px mono title bar):
  the posting with a pine inspector showing the evidence line, a 4-row fit matrix with verbatim
  quotes, a referral composer with a Gmail draft, and a resume diff with a form-fill status bar.
- **Changed from the brief, to stay true:** the status bar says "Live · refreshed every 3h", not
  "Live D1 stream" (D1 is retired and the page reads a 3-hourly snapshot); the inspector shows line
  12, where the requirement sits in the stored posting, not 42; the title bar shows the posting's
  real Lever URL; the draft is addressed to "Rohan K." with no made-up address at a real company;
  emerald and amber are fills under pine text, with darker shades for text (emerald-500 on white is
  2.5:1). One line above the steps says the resume and the people are a sample.

## 2026-10-23 — Landing page polish: graphite, light orange and white; Geist only
- **Choice (Shrey):** palette graphite, light orange and white (replaces Night and cornflower from
  earlier today); every heading in Geist Sans (Bricolage Grotesque dropped). Chapters alternate:
  graphite for the hero, globe and footer, white for the sources band and How it works. Tokens:
  `.lp-dark` / `.lp-light` in `globals.css`, `color.landingDark` / `landingLight` in `tokens.ts`.
  Light orange (#ff9e5e) is a fill under graphite text; as text it is #ffa46e on graphite and
  #b04a0e on white, to keep 4.5:1.
- **Brief (Shrey), applied:** no metric repeated across sections (hero badge keeps the fresher count;
  globe section shows hubs plus a "visa or relocation tagged" count; sources show pipeline numbers:
  3h between reads, 12+ hiring systems read directly, 0 LinkedIn or Indeed scraping); edge-faded
  marquees with monospace protocol chips and editorial company names; sticky 4-pill step switcher
  in How it works; file bar on the sample-resume cards; Git-style diff on step 4; highlighted
  evidence on step 1; monograms and a tactile button on step 3; the "Browse N fresher jobs" pill
  always in the top bar.
- **Where the brief bent a house rule, Shrey's words won:** monospace chips and pill numbers
  (taste-skill bans both), an arrow on the bar button, a shadow on the tactile buttons.
- **Changed from the brief, to stay true:** the alumni badge reads "Alumni · 2023 batch", not
  "Verified Alumni", since Kario verifies nothing about a connection; the file bar says "sample" so
  the example resume is never read as a real student's. "12+" counts the 13 adapters in `sources/`
  other than Hacker News.
- **New API field:** `/api/meta` gains `visa_or_relocation` (open roles with visa sponsorship or a
  relocation line), in the snapshot from the next pipeline run; until then the page leaves the
  figure out.

## 2026-10-23 — Landing page design: Shrey's layout, art-directed with taste-skill
- **Layout (Shrey):** glass top bar (kario, How it works, Jobs, profile); tagline "Not another job
  board. An agent that gets you your next job." beside a turning globe; on scroll the globe rolls
  left, turns to India and lights cities with live job counts ("Find jobs all around the globe");
  then a moving band of the hiring systems and companies we read; then How it works in four steps;
  a full-width kario wordmark closes the page. Built at `/preview` (`site/src/components/landing/`).
- **Globe options:** dotted (cobe, ~5 KB) · realistic textured (three.js, 150 KB+) · line drawing
  (d3-geo). **Choice:** dotted; a 37 KB still (`site/public/landing/globe.webp`) replaces it without
  WebGL or with Save-Data on.
- **Palette options** (taste-skill library; it bans indigo, so #5851ec had to be decided): keep
  indigo light · keep indigo on a dark page · new palette. Then Night and cornflower · Graphite and
  orange · Bottle ink and yellow. **Choice:** new palette, Night and cornflower (`.night` tokens in
  `globals.css`, mirrored as `color.night` in `tokens.ts`, checked by `check:tokens`). For now only
  the landing page uses it; the job list is restyled to match in its own change.
- **Headline face options:** Schibsted Grotesk Heavy · Bricolage Grotesque · Unbounded with Onest.
  **Choice:** Bricolage Grotesque 600, loaded by `app/preview/page.tsx` only, so the job list never
  downloads it; Geist stays for text.
- **Pictures options:** real Kario interface pieces in HTML · those plus credited city photos ·
  flat illustrations. **Choice:** interface pieces (`landing/Fragments.tsx`), following one real
  posting (Palantir new grad, 2026-10-23) with its real evidence; the profile behind fit, people and
  resume lines is an example and labelled so.
- **Glass:** taste-skill bans it and CLAUDE.md bans it "everywhere"; Shrey wants it on the top bar.
  Kept to that one bar.
- **What the steps promise** (copy must be true at launch): applying is prepared by the agent and
  submitted by you (options were: you submit · agent submits where an apply API exists · fully
  automatic); people to ask come from your uploaded LinkedIn export first, then public team pages
  (options: export · public pages · both). Email goes from your Gmail after approval; LinkedIn notes
  are sent by you.
- **Libraries (landing only):** cobe 2.0.1, GSAP 3.15 with ScrollTrigger and SplitText, Lenis
  1.3.25. Motion and React Three Fiber were not needed. The job list's JavaScript is unchanged.
- **taste-skill:** its rules and library were used by hand; its `draw`, `lint` and `inspect`
  scripts were blocked in this environment (external code), so checks were Playwright screenshots
  at 390, 768 and 1440 px, reduced motion, overflow and keyboard order.

## 2026-10-19 — Home page tells the whole story, launched only when it is all true
- **Options (purpose):** a pitch for signed-out visitors · a start screen for signed-in users ·
  both, split by state. **Options (before launch):** a hidden `/preview` route · Cloudflare preview
  URLs per PR · a long-lived branch
- **Choice (Shrey):** both, split by state (signed-in part comes with sign-in). The page tells the
  market story (our own count plus cited reports), the product (labels, fit, resume tailored to the
  JD, referral outreach), the impact and what you get. It is built at `/preview` (unlinked, noindex)
  and replaces `/` only when every feature it promises works end to end; then the list moves to
  `/jobs` and old `/?…` links redirect.
- **Look:** editorial with motion: a React Three Fiber hero on every device (still image for reduced
  motion, Save-Data or no WebGL), GSAP scroll story, a sans display face over Geist body text.
- **Why:** a page that promises unbuilt features would mislead; `/preview` keeps one codebase on
  `main` with no deploy changes.

## 2026-10-19 — Referral outreach: the agent drafts, the person sends
- **Options (LinkedIn):** agent drafts, user sends with one tap · a browser extension fills the box ·
  fully automatic sending. **Options (email):** drafts in the user's Gmail, approved before sending ·
  auto-send with a daily cap · copy and paste only
- **Choice (Shrey):** LinkedIn: the agent finds the person and writes the note; one tap copies it and
  opens the profile. Email: drafts go into the user's own Gmail (Google sign-in), and each is
  approved before it is sent.
- **Why:** LinkedIn's terms ban automated messaging and accounts get restricted; CLAUDE.md rules out
  automating LinkedIn. Nothing goes out under a student's name without them reading it.

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
