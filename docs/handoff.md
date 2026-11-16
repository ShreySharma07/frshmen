# Handoff (2026-11-16)

For whoever picks this up next. Read `CLAUDE.md` first, then this, then the 2026-11-15 and
2026-11-16 entries at the top of `docs/decisions.md`. Launch target: about 2026-11-27.

## Where things stand

Everything below is merged into `main` (PRs #72–#78).

**Site and routes**
- `/` is the landing page, `/jobs` the job list. Old `/?…` links go on to `/jobs` with their filters.
- A signed-in person opening `/` from outside goes to `/jobs`. The Aventra logo (sidebar, phone top
  bar) always opens the landing page; `HOME_KEY` in `sessionStorage` (`lib/session.ts`) tells `/`
  not to redirect.
- Page scroll: the agent chat scrolls with the page (no inner scroll box); browser scroll bars are
  the browser's own; the open job pane on wide screens hides its own bar.
- Native dropdowns: every `option`/`optgroup` takes the theme colours (`globals.css`), so they read
  on Windows dark mode.

**Profile (layout A)**
- Experience: five bands (0–1, 1–3, 3–5, 5–8, 8+), saved as 0, 2, 4, 6, 8.
- Work wanted: any of the 14 job categories (`students.target_roles`, migration `0016`).
- Live preview of the job list it gives (count on phones, first jobs beside the form on wide
  screens).
- `/api/jobs?category=` and the site's `cat=` take a comma list.

**Agent**
- Opens on "Your chats" (saved chats in the middle, New chat above). A new chat starts with the box
  in the middle; the first message glides it to the bottom (Motion `layoutId`).
- Chats saved in `agent_chats` (migration `0017`): own rows only, last 30, kept 15 days, revealed
  email addresses never stored.
- Tools: `search_jobs`, `find_people`, `suggest_startups`, `prepare_draft`, `find_connections`,
  `prepare_linkedin_message`.
- A 5xx from Gemini falls back to the next model; if all are busy the person sees "Gemini is busy".

**LinkedIn and Gmail (both working, per Shrey)**
- `Connections.csv` upload on the profile → `connections` (migration `0015`), emails dropped.
- "Continue with LinkedIn" behind repo variable `LINKEDIN_SIGNIN=on`.
- "Send from Gmail" behind repo variable `GOOGLE_CLIENT_ID` (same Google client as sign-in);
  browser-only `gmail.send` token, never stored. Unverified app: up to 100 test users.

## Next, in this order

1. **Legal pages** (recommended next): Privacy, Terms, Refunds and cancellation, Contact.
   - Razorpay's account review usually asks for them.
   - Google's Gmail verification needs the privacy page.
   - They must cover: chats (15 days), LinkedIn connections, the contact lists, resumes, Gmail
     sending, and the no-refund policy.
   - Ask Shrey who the operator is (name, contact email, city) before writing.
2. **Premium with Razorpay subscriptions.** The plan is decided and written in
   `docs/strategy/premium/plan.md`, with a diagram in `architecture.png` there.
   - Pricing: ₹99 a month or ₹249 every 3 months.
   - Premium covers the Agent, tailored resumes, and fit checks beyond 3 a day.
   - Free covers Jobs, the profile, Applications and Insights.
   - The plan has 25 edge cases; four are required before launch.
   - The build is about 5 days, starting with migration `0018_billing.sql` and `is_premium`.
   - Everything stays behind `PREMIUM=on` until Shrey's Razorpay account is approved.
3. Own domain; a pipeline failure alert. (The budget-Android test was skipped by Shrey.)

## Waiting on Shrey

- Razorpay: account and KYC (as an individual), switch on Subscriptions, create the two plans, add
  the webhook, put the keys in Worker secrets (steps in the plan, section 5).
- Check on the live site: the Windows dropdowns, the centred chat box, and that the Supabase
  migrations workflow ran green for `0015`–`0017`.

## Working notes

**Process**
- Branch `claude/beautiful-einstein-th8qpc`, draft PRs. Shrey merges fast: push everything before
  saying a PR is ready (twice now a merge landed before the last commits; see #76).
- UI changes: 2–3 low-fidelity sketches first (`docs/wireframes/…`, phone and desktop), Shrey picks,
  then build; screenshots at 390 and 1280 px, light and dark.
- Architecture or money choices: options with pros and cons, a recommendation, wait for Shrey, log
  in `docs/decisions.md`.
- Shrey's preferences: short, to-the-point answers; an analogy when explaining; ask before big
  changes.

**Tests**
- `python -m pytest -q` needs `PG_TEST_URL` (654+ pass with it).
  - Start a throwaway Postgres 16 under `/var/tmp`. The scratchpad isn't readable by the `postgres`
    user.
  - `initdb` and `pg_ctl` live in `/usr/lib/postgresql/16/bin`.
  - The server sometimes stops between commands; start it again.
- Site: `cd site && npm run typecheck && npm run lint && npm run build`. Build with placeholder
  `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
- Signed-in screenshots: store a fake session in `localStorage` (`sb-placeholder-auth-token`), mock
  Supabase REST and `/api/*` with Playwright routes, and serve `site/out` with `/x` → `x.html`.
  `/api/meta` mocks need `countries` and the other arrays.
- The live site isn't reachable from this sandbox (proxy refuses it).
