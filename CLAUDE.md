# CLAUDE.md — Personal AI/ML Fresher Job Board

## What this project is
A personal job board for one user (Shrey). It polls company hiring sources continuously, extracts structured data from each posting, and lists **every open job** on a web page, newest first, 20 per page, with filters for fresher/internship/0–N years/experienced, role, location and visa (decided 2026-10-08, see `docs/decisions.md`). Accuracy of the labels is the whole point: if a posting says "2+ years" anywhere in the description, it must NOT be labelled fresher.

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
1. **Discover** companies and their ATS (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday, Eightfold, Oracle Recruiting, plus company career sites read through their sitemap and schema.org job data, YC and Hacker News "Who is hiring").
2. **Fetch** postings via each ATS's public JSON endpoint on a schedule.
3. **Normalize** to one schema (see below). Dedupe.
4. **Extract** experience, batch year, location type, visa sponsorship, skills via rules (see `skills.md`). No LLM in the pipeline.
5. **Classify** into `fresher` / `maybe` / `experienced` with confidence + evidence.
6. **Publish** classified jobs to Supabase Postgres; the web page reads them through the Python API (see `docs/decisions.md`). New postings are flagged with first-seen time.

## Core schema (starting point; propose changes via decisions.md)
`id`, `source`, `company`, `title`, `url`, `location_raw`, `location_type` (remote/hybrid/onsite), `countries`, `posted_at` (if the source gives it), `first_seen_at`, `description_text`, `yoe_min`, `yoe_max`, `yoe_evidence`, `batch_years`, `level` (fresher/maybe/experienced), `level_confidence`, `visa_sponsorship` (yes/no/unknown), `skills`, `match_score`, `status` (open/closed), `content_hash`.

## Architecture (decided; full rationale in `docs/decisions.md`)
- Pipeline: Python, run by GitHub Actions cron
- Storage: Supabase Postgres (+ Supabase Auth later) since 2026-10-16; schema in `db/postgres/`, applied by the Supabase migrations workflow. Free tier: 500 MB DB, 50k MAU, pauses after 1 week idle, so write only new/changed rows. D1 is no longer written; its database is kept until ~2026-10-23 as a backup, then deleted
- Backend API: FastAPI on Cloudflare Python Workers, reading Supabase Postgres through Hyperdrive with asyncpg (2026-10-16; free: 100k requests/day, 100k queries/day, 10 ms CPU per request).
- Frontend: React (Vite + TypeScript) today. **Moving to Next.js (React + TypeScript)** (2026-10-15), web first and a mobile app later; see "Frontend standards" below
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

## Frontend standards (read before any UI work)
The site must look designed by a person with taste, not generated. Web first; a mobile app
(React Native/Expo) comes later and reuses the API client, types and design tokens.

### Banned ("AI slop" tells)
- Purple/blue gradient heroes, glassmorphism everywhere, glowing blobs, and "bento grid" by default.
- Generic copy ("Supercharge your career", "Unlock your potential"), emoji bullet lists, and
  sparkle icons for anything AI.
- Stock 3D illustrations and random floating shapes.
- Default shadcn/Tailwind look shipped unstyled, and Inter on everything.
- Motion with no purpose: everything fading up on scroll, or parallax for its own sake.
- Placeholder content. Show real jobs, real counts and real evidence snippets.

### Design system first
- **Tokens are written before components**, in one place (CSS variables, mirrored in a TS file for
  the future mobile app):
  - colour: a small palette with one accent and semantic roles, with dark mode designed, not
    inverted
  - a type scale
  - spacing
  - radius
  - elevation
  - motion durations and easings
- **Typography:** at most two families. A distinctive display face (e.g. from Fontshare or Google
  Fonts) and a highly legible text face, self-hosted with `next/font`.
- **Styling:** Tailwind CSS v4 on top of the tokens.
- **Component behaviour:** Radix Primitives or React Aria (accessible menus, dialogs, tabs).
  shadcn/ui is fine as a starting point only if it's restyled to our tokens.
- **Icons:** one set only (Lucide or Phosphor), one stroke weight.

### Motion and graphics toolkit (pick the lightest tool that does the job)
| Need | Tool |
|---|---|
| UI state: enter/exit, layout shifts, shared-element card → detail, gestures | **Motion** (`motion/react`, formerly Framer Motion) |
| Route/page transitions | **View Transitions API** (supported in Next.js), with Motion as the fallback |
| Scroll storytelling, pinned sections, text reveals on the landing page | **GSAP** + ScrollTrigger + SplitText (all free for commercial use since GSAP 3.13) |
| Smooth scrolling | **Lenis**, on the landing page only, never on the job list |
| Cheap scroll-linked effects | CSS scroll-driven animations (`animation-timeline`) |
| Interactive vector animation (mascot, empty states, onboarding) | **Rive** (state machines; smaller than Lottie); Lottie only for simple one-off icons |
| 3D hero moment | **React Three Fiber** + drei, lazy-loaded, with a static image fallback; landing page only |
| Data visuals (skill heatmaps, trends) | Visx or plain SVG, styled with our tokens |

### Motion rules
- **Every animation explains something:** where an item came from or went, what changed, what is
  loading. If it explains nothing, remove it.
- **Durations:**
  - 150–250 ms for UI feedback
  - 300–500 ms for layout and route changes
  - up to ~800 ms for one-off landing moments
- **Easing:** consistent curves from the tokens. No linear easing on UI, and no bounce on serious
  actions.
- **Animate only `transform` and `opacity`** (and `clip-path` sparingly). Never animate layout
  properties.
- **Respect `prefers-reduced-motion`.** Every animation has a reduced or no-motion version.

### Performance budget (students are on budget Android phones and patchy 4G)
- Job list route:
  - LCP under 2.5 s on throttled 4G
  - under ~170 KB of JavaScript (gzip)
  - INP under 200 ms
- GSAP, Lenis, Three.js and Rive load **only** on the routes that use them (dynamic import).
- Test on Chrome DevTools with 4× CPU throttle and "Fast 4G", plus one real low-end Android, before
  shipping UI.

### Process for every UI change
1. **Brief:** what the screen is for, the one thing the user must do, and real content samples.
2. **References:** look at real products for the pattern (Mobbin, Godly, Awwwards, and products
   like Linear, Vercel, Stripe, Raycast). Borrow the idea, never the look.
3. **Sketch:** a low-fidelity wireframe, shown to Shrey before styling.
4. **Build:** tokens → layout → content → motion, last.
5. **Check:**
   - Playwright screenshots at 390 px and 1280 px, light and dark
   - keyboard navigation
   - WCAG AA contrast
   - the performance budget above
6. **Learning:** Shrey builds as much as he can first. Claude explains with an analogy, then gives
   hints, then (only if needed) the answer, never code first.

