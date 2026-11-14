# Handoff (2026-11-14)

For whoever picks this up next. Read `CLAUDE.md` first, then this, then the last entries of
`docs/decisions.md`. Launch target: about 2026-11-27.

## Where things stand

Everything below is merged into `main` (last PRs #65–#70).

**Jobs and labels**
- Years written in a title count as a requirement ("Software Engineer | 8-12 yrs" can't be fresher).
- Level codes (SDE III, L5+, Head, Snr…) count as senior; level II stays neutral.
- Experience **bands** (0–1, 1–3, 3–5, 5–8, 8+) drive the "I have" filter: `/api/jobs?band=`.
- Every job has a general **category** (14 kinds, `config/role_families.yaml`, `extract/category.py`):
  `/api/jobs?category=`. `role_family` still means "which of Shrey's target roles matched".
- `EXTRACT_VERSION` is 6.

**Admin (`/admin`, admins only)**
- Overview: open jobs, users, sign-ups, AI use, jobs by category/band/source, the last pipeline runs.
  The Visits card links to Cloudflare Web Analytics.
- Add a job by hand: stored in `manual_jobs`; the pipeline reads it as source `manual` and labels it
  like every job.
- Contact lists: CSV upload for HR and YC founders (preview, then save; delete one email or a whole
  upload). Stored in `contacts`, never readable from the browser.
- Admins live in the `admins` table, added by hand in the Supabase SQL editor:
  `INSERT INTO admins (user_id) SELECT id FROM auth.users WHERE email = 'you@example.com';`

**Agent (`/agent`)**
- Chat tab first, then Today (the old page).
- Backend `POST /api/agent/chat` (`api/src/agent.py`): Gemini with four tools: `search_jobs`,
  `find_people`, `suggest_startups`, `prepare_draft`.
- Limits: 20 messages a day per person (`agent_messages`), and 5 email addresses a day
  (`contact_reveals`).
- **Privacy rule (tested):** Gemini never sees an email or a phone number. The server adds the
  address to a draft; phones never leave the database.
- Drafts open beside the chat like a document (a sheet on phones): edit, copy, "Open in Gmail".
- It uses the fit check's settings: Worker var `FIT_CHECK=on` and secret `GEMINI_API_KEY`.

**Site**
- The landing hero marigold bug is fixed: a global `.hl` class collided; the job card's class is now
  `.mark-sweep`.
- On wide screens, search is the bottom command bar only; `/` opens it. Phones keep the Jobs search
  box. No command bar on `/agent`.
- Spinners on upload and save buttons.
- Cloudflare Web Analytics token comes from repo variable `CF_BEACON_TOKEN` (`site/.env.example`).

## Waiting on Shrey (not code)

1. **Upload the contact lists:** `/admin` → Contact lists. YC founders headers like
   `Founder Name,Email,Company,Title,YC Batch,Company Status,…` are now read.
2. **Try the agent with real data.** It has only been tested against a fake Gemini. Report wrong
   people, weak drafts or slow replies.
3. **Check settings:**
   - Repo variable `CF_BEACON_TOKEN` is set.
   - The Supabase migrations workflow ran green for `0011`–`0014`.
4. **Allow the weekly detection PR:** tick Settings → Actions → General → "Allow GitHub Actions to
   create and approve pull requests". Without it, `detect-careers-weekly` fails at its last step.

## Next, in the plan's order (`docs/strategy/agent-admin-launch.md` §6)

Decisions already made are in `docs/decisions.md` (2026-11-13 and 2026-11-14).

1. **Fix whatever the first real agent conversations show.** The prompt is `SYSTEM` in
   `api/src/agent.py`.
2. **Gmail:**
   - Launch uses "Open in Gmail" with a filled-in link: done.
   - Next, apply for Google verification of `gmail.send` (sensitive scope, no paid audit), then send
     from Aventra.
   - Never `gmail.compose` (restricted, ~$500/yr audit).
3. **LinkedIn:**
   - "Sign in with LinkedIn" for login and profile only.
   - Upload of LinkedIn's own `Connections.csv` for "who do I know at X".
   - No connections API exists for us; never automate LinkedIn.
4. **Apollo:** each person connects their own key (free tier: 900 credits a year, licence covers
   their own use). Cut first if time runs short.
5. **Launch list:**
   - landing page to `/` (it lives at `/preview`) and the job list to `/jobs`;
   - profile form for every band and all 14 categories (it still caps years at "3+" and offers 3
     roles);
   - privacy policy and terms (DPDP Act, contact data);
   - own domain;
   - a pipeline failure alert;
   - test on a real budget Android.
6. **Later:**
   - The Oracle, SmartRecruiters and career-site readers fetch only target-like roles, so other
     categories are thin for their companies (a separate decision).
   - Per-user target roles.

## Working notes

**Process**
- Branch `claude/jolly-edison-0h382a`, draft PRs.
- Shrey merges fast. Push everything before telling him a PR is ready: once, #68 was merged a minute
  before the last commits landed, and they needed a follow-up PR (#69).
- For each UI change, show 2–3 low-fidelity wireframes first (see `docs/wireframes/admin/` and
  `docs/wireframes/agent/`), let Shrey pick, then build. Screenshot at 390 px and 1280 px, light and
  dark.
- Keys and tokens of outside services never go in source, even public ones: use the environment and
  `.env.example` (rule in `CLAUDE.md`).

**Tests**
- `python -m pytest -q` needs `PG_TEST_URL` for the API, admin, agent and RLS tests. Without it,
  ~145 are skipped.
- Locally, a throwaway Postgres 16: `initdb` and `pg_ctl` under `/usr/lib/postgresql/16/bin`, run as
  the `postgres` user, then:
  `PG_TEST_URL=postgresql://postgres@localhost:5432/postgres python -m pytest -q`
  (641 passed at handoff).
- Site checks: `cd site && npm run typecheck && npm run lint && npm run build`.
- To screenshot signed-in pages, build with placeholder `NEXT_PUBLIC_SUPABASE_URL` and
  `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, store a fake session in `localStorage`, and mock `/api/*`
  with Playwright routes.

**Known CI noise**
- The `fetch` smoke test fails when NVIDIA's Workday site is down: HTTP 521, or an empty search.
  That is outside us; the PR comment on #67 explains it.
- Darwinbox refuses GitHub's runners. Those companies stay `verified: false` on purpose.
