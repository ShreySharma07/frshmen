# Handoff (2026-11-18)

For whoever picks this up next. Read `CLAUDE.md` first, then this, then the newest entries of
`docs/decisions.md` (2026-11-16 to 2026-11-18). Launch target: about 2026-11-27.
Replaces the 2026-11-14 handoff.

## Where things stand

Merged into `main` since the last handoff: PRs #81–#89. Open: #90 (UI fixes, CI green, waiting
for Shrey to merge).

**Agent**
- YC startups ranked by fit with the person's kinds of work and resume skills, openings or not
  (`startup_profiles`, filled weekly by `scripts/refresh_startups.py`: the CSV description, then
  yc-oss, then the startup's homepage meta description). 12 by default, up to 50, "show more".
- Email drafts follow a fixed shape (subject under 8 words, 1–2 relevant projects, one ask, under
  120 words). The server refuses drafts over 150 words, with stock filler, or naming none of the
  resume's skills.
- A draft may only address someone found in the same reply. Caps: 5 email reveals per person a
  day, 3 per contact a day across everyone, 300 a day site-wide.
- #90 adds `open_resume_editor`, so "customise my resume" typed in the chat opens the editor.

**Resume**
- Structure read from the uploaded PDF (`site/src/lib/pdfLines.ts`, `resumeDoc.ts`): headings,
  entries with right-aligned dates, bullets (Word's bullet characters too), wrapped lines.
  Stored in `students.resume_doc`; `resume_text` is written from it.
- The editor beside the agent chat has two tabs:
  - **Content:** fields, plus "Ask agent to improve", which puts each reworded line back into its
    field.
  - **Design:** four Typst templates (Classic, Modern, Compact, Sidebar labels), a preview, and
    Download PDF.
- Typst runs in the browser in a worker: an 11 MB gzip compiler, downloaded once and cached,
  built by `site/scripts/typst-assets.mjs` before each build.

**Security (review in `docs/strategy/system-design-review.md`)**
- H1: daily limits count a hash of the person's email in `usage_events`, so deleting the profile
  or the account doesn't reset them. One per-person lock also fixes the reveal race (L1).
- M1: contacts can't be harvested (same-reply rule and caps). Turnstile on email sign-in links,
  switched on by a variable.
- M2: `api/src/edge.py` adds per-IP rate limits (120 a minute on the API, 10 a minute on Gemini
  routes) and a 5-minute edge cache for anonymous public GETs. Paging stops at 2,000 jobs. HEAD
  works. Confirmed live: `miss`, then `hit`.
- M3: a daily `measure-storage` run fails past 80% of the free 500 MB (GitHub emails the owner).
  Chat limits unchanged (Shrey).
- M4: emails and phone numbers are stripped from every resume sent to Gemini and restored in the
  person's PDF. "Delete everything" calls `delete_my_account()`, which removes the sign-in too.
- Next.js 16.4.6: 0 production npm advisories.

## Waiting on Shrey (settings, not code)

1. **Merge #90.**
2. **Migrations:** check the Supabase migrations workflow ran green for `0018`–`0021`.
3. **Run Actions → Refresh startups** once (and again after each new founders CSV). Until then
   the agent says "couldn't tell what they build" for every startup.
4. **Repo secret `USAGE_HASH_KEY`** (`openssl rand -hex 32`). Set it once and never change it:
   a new key resets everyone's daily counts.
5. **Turnstile, in this order** (`docs/setup-auth.md` step 7):
   1. Create the widget in Cloudflare.
   2. Add the repo variable `TURNSTILE_SITE_KEY` and redeploy.
   3. Only then turn on CAPTCHA in Supabase (Attack Protection) with the secret key.
   Doing step 3 first breaks email sign-in until the next deploy.
6. **Once the own domain is on Cloudflare:**
   - add the rate-limit rule in `docs/setup-rate-limit.md`;
   - add the domain to the Turnstile widget, Supabase redirect URLs and Google OAuth origins.
7. **From the old handoff, still open:**
   - upload the HR and YC founder CSVs in `/admin`;
   - try the agent with real data;
   - tick Settings → Actions → General → "Allow GitHub Actions to create and approve pull
     requests", needed by `detect-careers-weekly`.
8. **Try the resume editor** with your own PDF and report anything it reads wrong. Each wrong
   read becomes a test (`site/tests/`).

## Left to build, in launch order

1. **Legal pages:** Privacy (includes M4's privacy notice), Terms, Refunds and cancellation,
   Contact. Needed by Razorpay and for Google's `gmail.send` verification. Ask Shrey first, then
   write them:
   - Who runs Aventra (individual, sole proprietor or company) and the legal name to show.
   - Contact email, postal address and phone. Razorpay wants all three public; a city and state
     is the minimum.
   - Grievance Officer's name and email (DPDP Act and IT Rules).
   - Which city's courts handle disputes.
   - Minimum age. 18+ is simplest; under-18s need verifiable parental consent under DPDP.
   - The removal address for people in the contact lists.
   - Refunds: the decision is no refunds and cancelling stops the next charge. Proposed
     exceptions: double charges, and failed payments where money was taken, refunded in 5–7
     working days to the original method.
   - Whether to add a Shipping/Delivery page ("digital, access starts at once").
   - Domain and effective date, until the own domain exists.
   - Facts for the Privacy page:
     - What is stored: profile, resume PDF and text, `resume_doc`, chats (30, 15 days),
       connections.
     - What is sent to Google Gemini: resumes without email or phone; connection names and
       titles.
     - What is kept after deletion: the email-reveal log (id cleared) and 48-hour usage hashes.
   - Not legal advice: Shrey to have them checked.
2. **Low-severity security items** (one PR, code only; details in the review's table):
   - L2: security headers (CSP `frame-ancestors`, `nosniff`, `Referrer-Policy`) in
     `site/public/_headers`, plus an API middleware.
   - L3: in `deploy.yml`, the Cloudflare token only on the deploy step; pin wrangler;
     `permissions: contents: read`; actions pinned by SHA.
   - L4: `detect-careers.yml` should pass `inputs.only` through `env:`.
   - L5: return a generic 500 with a request id; explicit columns from `runs` in `/api/meta`;
     `/api/docs` off in production.
   - L6: pin the Python dependencies and add a lock file.
   - L7: the pipeline HTTP client should allow only `http(s)`.
   - L8: drop non-`http(s)` job URLs at publish, plus a CHECK.
   - L9: escape `%` and `_` in the job search (reuse `agent._like`).
   - I2: the Hyperdrive id in `api/wrangler.jsonc` breaks the "no ids in source" rule; inject it
     at deploy or record an exception.
3. **Launch list leftovers** (from `docs/strategy/agent-admin-launch.md`):
   - the own domain;
   - a pipeline failure alert;
   - Resend for email (`docs/setup-auth.md` step 6);
   - a test on a real budget Android: the first Design-tab visit downloads ~12 MB, so time it
     on 4G.
4. **Gmail send:** apply for Google verification of `gmail.send`, which needs the privacy policy
   and the domain. Never `gmail.compose`.
5. **Premium with Razorpay:** planned, not built (`docs/strategy/premium/plan.md`; ₹99 a month or
   ₹249 every 3 months, renewing). Four edge cases must be in before launch:
   - no double charges;
   - `/verify` only for your own subscription;
   - cancel on Razorpay before an account is deleted;
   - refunds and disputes end Premium.

   New tables must reference `auth.users`, not `students`, or deleting a profile could wipe
   them (the H1 lesson). Webhooks must be signed and stored once, by event id.
6. **Design review leftovers** (need a decision first):
   - a weekly encrypted database backup (the free plan has no point-in-time recovery);
   - a Gemini "quota exhausted" circuit breaker;
   - `pg_trgm` for search if it gets slow.
7. **Later:** wider fetching for the Oracle, SmartRecruiters and career-site readers; per-user
   target roles.

## Working notes

**Process**
- Develop on the branch the session names (this one: `claude/eager-franklin-j1wi33`) and open
  draft PRs. Shrey merges fast; push everything before saying a PR is ready.
- After a PR merges, restart the branch from `main` for the next one, so each PR is one concern.
- **UI changes:** wireframes first (`docs/wireframes/`), Shrey picks, then build. Screenshot at
  390 px and 1280 px, light and dark.
- **Architecture, schema and infrastructure:** options first, Shrey decides, then log it in
  `docs/decisions.md`.
- **Secrets:** keys and ids of outside services never go in source. Use the environment, and list
  each in `.env.example` or the setup docs.

**Tests**
- Python: `PG_TEST_URL=postgresql://postgres@localhost:5432/postgres python -m pytest -q`
  (696 passed). A throwaway Postgres 16 in a fresh container:
  ```
  useradd -m postgres; mkdir -p /tmp/pgdata && chown postgres /tmp/pgdata
  su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /tmp/pgdata -A trust"
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pgdata -l /tmp/pgdata/log -o '-k /tmp' start"
  pip install -r requirements-dev.txt
  ```
- Site: `cd site && npm ci && npm run typecheck && npm run lint && npm test && npm run build`.
  `npm test` runs `site/tests/*.test.ts` with Node's own runner: the resume reader and the four
  templates compiled in Node.
- **Screenshots of signed-in pages:**
  - build with placeholder `NEXT_PUBLIC_SUPABASE_URL=https://demo.supabase.co` and
    `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`;
  - serve `site/out` from a Playwright route on `https://app.test` (https, because
    `crypto.randomUUID` needs a secure origin);
  - store a fake session under `sb-demo-auth-token` in localStorage;
  - mock `demo.supabase.co` and `/api/*`. Mock jobs need the full `JobSummary` shape, or the
    page crashes.
- **The cache in production:** `curl -s -o /dev/null -D - <site>/api/meta | grep -i
  x-aventra-cache` should show `miss`, then `hit` (HEAD works too since #88).

**Known noise**
- The `fetch` smoke test fails when NVIDIA's Workday site is down (HTTP 521). Darwinbox refuses
  GitHub's runners; those companies stay `verified: false` on purpose.
- In an agent sandbox, `next build` may stop once with a Next.js security notice. Running it again
  continues. It was cleared by 16.4.6 but can come back with a new advisory: upgrade in its own PR.
- `npm audit` lists 14 dev-only "high" (glob ReDoS under `eslint-config-next`); npm's only fix is
  a downgrade. Nothing ships to users.
