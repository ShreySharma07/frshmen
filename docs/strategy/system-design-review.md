# System design review (2026-11-18)

What Aventra uses today, what it is missing, and what is worth adding before launch (~2026-11-27).
Scale assumed: hundreds to a few thousand people, on free tiers (Cloudflare Workers 100k requests
and 100k Hyperdrive queries a day, 10 ms CPU per request; Supabase 500 MB, pauses after a week idle;
Gemini free tier). Security has its own section at the end, from a separate read-only review.

## The shape, in one picture

```
GitHub Actions (cron) ──fetch──▶ job boards        (batch writer, every ~3 h)
        │ writes changed rows only
        ▼
Supabase Postgres ◀── RLS ── browser (supabase-js: profile, chats, connections, resume)
        ▲
        │ Hyperdrive (pooled connections)
Cloudflare Worker: FastAPI /api/*  +  static site (Next.js export)  ── Gemini (fit, tailor, agent)
```

Analogy: a newspaper. The pipeline is the night shift that prints the paper (batch, on a schedule);
the Worker is the newsstand that hands out copies (many readers, same paper); Postgres is the archive.
Most design choices below follow from "one writer, many readers, content changes every few hours".

## Pattern by pattern

| Pattern | Analogy | What we have | Gap | Do now? |
|---|---|---|---|---|
| **Conditional fetching** (ETag / If-Modified-Since) | Asking "anything new since Tuesday?" instead of re-reading the book | `sources/http.py` stores ETags and asks before re-downloading; per-job detail calls reuse a stored copy | none | — |
| **Edge / CDN caching of static files** | Copies of the paper at every newsstand | The Next.js export is served as Worker static assets from Cloudflare's edge; hashed Typst files cached a year (`site/public/_headers`) | `_headers` covers only `/resume/*`; Next's hashed `/_next/static/*` relies on defaults | Low |
| **API response caching** | Photocopying the front page once, not re-typing it per reader | None: every `/api/jobs`, `/api/meta`, `/api/evidence` call runs SQL, though the answer only changes when the pipeline publishes | Each visitor costs a Worker request **and** DB queries against the 100k/day caps | **Yes**: `Cache-Control: public, s-maxage=300` + the Worker Cache API on the public GETs (anonymous only) |
| **Connection pooling** | A taxi rank instead of calling a cab per trip | Hyperdrive pools Postgres connections for the Worker | Hyperdrive can also cache read queries (default on for SELECTs, ~60 s); not configured explicitly, so verify it is on and that personal reads aren't affected | Check |
| **Precomputed / denormalised reads** | A ready index at the back of the book | `job_labels.is_current`, `refresh_current` in the pipeline; `job_cards` is a plain **view** (joined on every read); descriptions moved to Storage (`job_text`) | `/api/meta` counts and `job_cards` joins run per request | Later: a summary table written by the pipeline, if `/api/meta` gets slow |
| **Rate limiting: outbound** | Not knocking on the same door twice a second | Per-host pacing (2 s, 5 s for strict hosts), exponential backoff honouring `Retry-After` | none | — |
| **Rate limiting: per user** (quotas) | A ration card | Server-side 24 h sliding windows: fit checks 5, tailored 2, agent 20, email reveals 5; failed AI calls refunded | none for signed-in features | — |
| **Rate limiting: per IP / global** | A bouncer at the door | None on public endpoints (`/api/jobs`, `/api/evidence`, `/api/meta`) or on unauthenticated paths | One script can burn the daily Worker/Hyperdrive allowance and take the site down for everyone (free-tier DoS) | **Yes**: one Cloudflare WAF rate-limiting rule on `/api/*` (the free plan includes one), plus the cache above |
| **Concurrency: pessimistic locks** | One cashier per till | Quotas lock the person's `students` row (`SELECT … FOR UPDATE`) so two clicks count one after the other | Email reveals count in their own transaction without that lock (agent.py), so two messages sent at once could pass the cap of 5 | **Yes** (small): lock the same row before counting reveals |
| **Concurrency: batch jobs** | Only one night shift at a time | GitHub `concurrency: group: pipeline` stops the pipeline, backfills and compaction overlapping; ThreadPool fetches with per-host locks | none | — |
| **Optimistic concurrency** (version checks) | "Someone edited this since you opened it" | None: two tabs editing the resume or a chat, the last save wins | Rare for one person | Later |
| **Idempotency** | A receipt number so a payment isn't taken twice | Contact CSV upsert on email; chats upsert on id | Razorpay webhooks and `/verify` must store each event once (the premium plan says so, not built); "Send from Gmail" double-click | **Yes, with Razorpay** |
| **Retries, fallback, circuit breaker** | Trying the next shop; putting up "closed" instead of everyone queuing | Fetch retries with backoff; Gemini falls back to the next model on 404/5xx | No circuit breaker: when Gemini's daily quota is gone, every user still waits for a failing call | Soon: remember "Gemini exhausted" for ~60 s and answer at once |
| **Pagination** | Page numbers vs a bookmark | OFFSET pages of 20 | Deep pages scan and skip; fine below ~10k open jobs. `/api/evidence` does `ORDER BY random()` over every open job per call | Cache `/api/evidence`; keyset paging only if needed |
| **Indexes / search** | The book's index | Indexes on recency, company, status, quotas, contacts; `title ILIKE '%…%'` search | `ILIKE` with a leading `%` can't use a b-tree, so search is a full scan | Later: `pg_trgm` GIN index if search passes ~100 ms |
| **Partitioning / sharding** | Splitting the archive across buildings | Vertical split already: long descriptions in Storage, rows in Postgres; old descriptions compacted | Sharding is for millions of users or terabytes; we are at megabytes | **No.** First steps if ever needed: archive closed jobs, partition `jobs` by status/date |
| **Horizontal scaling** | More counters open when the queue grows | Workers scale per request on their own; the API is stateless (JWT, no server session) | The single Postgres is the one shared bottleneck | — |
| **Queues / async work** | A ticket queue at the deli | Cron batches; none in the request path (AI calls run inline, ~2–10 s) | Fine at our size | No |
| **Observability and alerts** | Smoke alarms | `runs` table + `/admin`, Cloudflare Web Analytics | No alert when the pipeline fails, Supabase pauses, or the API errors; API exceptions only in Worker logs | **Yes**: pipeline failure alert (on the launch list); a free uptime ping on `/api/meta` |
| **Backups / recovery** | A copy of the archive in another building | Supabase's own (free plan: no point-in-time recovery) | No backup we control; a bad migration or deletion is not recoverable | **Yes**: a weekly encrypted `pg_dump` from Actions (personal data: encrypt, short retention) |
| **Data lifecycle** | Shredding old files | Chats trimmed to 30 / 15 days; descriptions compacted; account deletion cascades | No stated retention for `contact_reveals`, `agent_messages`, `fit_checks` | Decide with the privacy policy |
| **Feature flags / kill switches** | A fuse box | `FIT_CHECK`, `PREMIUM`, `LINKEDIN_SIGNIN`, `GOOGLE_CLIENT_ID` | none | — |

## What to add before launch, in order

1. **Cache the public API** (`/api/jobs`, `/api/meta`, `/api/evidence`) at Cloudflare's edge for a few minutes. Biggest win: fewer Worker requests and DB queries, faster pages on 4G, and most of the DoS risk gone.
2. **One rate-limiting rule** on `/api/*` in Cloudflare (free plan: one rule).
3. **Lock before counting email reveals** (same row lock as the other quotas).
4. **Alerts**: pipeline failure, Supabase paused, API error rate.
5. **Weekly encrypted backup** of the database.
6. With Razorpay: **idempotent webhooks** (store each event id once).

Each of these is small (hours, not days). 1, 2 and 5 touch infrastructure, so they go through
`docs/decisions.md` with options first.

## Security review (2026-11-18, read-only)

Overall: **medium risk**. Authentication is checked by Supabase on every request, all SQL is
parameterised, RLS is on for every table with column-level grants, admin routes are gated in one
place, the agent's tools are bound to the server-side user, Gemini never sees emails or phones,
there are no XSS sinks for untrusted text, and no secrets are committed. The weak spot is abuse.

| ID | Severity | Issue | Fix |
|---|---|---|---|
| H1 | **High** (confirmed) | A user can delete and re-create their own `students` row through the Data API (`0004`: DELETE and INSERT granted). The usage tables (`agent_messages`, `contact_reveals`, `fit_checks`, `tailored_resumes`) reference `students ON DELETE CASCADE`, so this resets every daily limit and erases the reveal log. Unlimited Gemini use (the shared free quota) and unlimited email reveals. | Usage rows reference `auth.users`, or a separate usage ledger that outlives the profile; keep `contact_reveals` (audit log) from cascading; RLS test: delete + re-insert the profile, the counters survive. |
| M1 | Medium | `prepare_draft` accepts any `contact_id` (sequential), so a script with many free accounts can harvest 5 emails per account per day; with H1, unlimited. | H1; CAPTCHA (Cloudflare Turnstile, free) and email confirmation at sign-up; reveal only contacts the same request found; a global per-day cap and an admin alert; agent behind Premium as planned. |
| M2 | Medium | Public endpoints (`/api/skill-demand`, `/api/evidence` with `ORDER BY random()`, deep `/api/jobs` pages) run full scans with no cache or rate limit. | The edge cache and rate-limit rule above; cap `page × per_page`. |
| M3 | Medium | One account can store about 9 MB (chats 30 × 256 KB, 5,000 connections, resume_doc 128 KB): ~55 throwaway accounts fill the 500 MB database and block writes for everyone. | Lower the chat size and count; CAPTCHA; a size alert from `measure-storage`. |
| M4 | Medium | Resumes (with the person's email and phone) and connection names go to Gemini's free tier, which Google may use to improve products; no privacy notice yet; "Delete everything" leaves the `auth.users` row. | Strip email and phone before Gemini; the privacy policy (next); a server-side account delete that removes the Auth user. |
| L1 | Low (confirmed) | The email-reveal count isn't under the row lock the other quotas use: parallel messages can pass 5. | Lock the person's row first in that transaction. |
| L2 | Low | No security headers: CSP, `frame-ancestors`, `nosniff`, `Referrer-Policy`. | Add them in `_headers` and an API middleware. |
| L3 | Low | Deploy workflow exposes `CLOUDFLARE_API_TOKEN` to every step (incl. `npm ci` scripts and an unpinned `npx wrangler`); no `permissions:` on some workflows; actions pinned by tag. | Token on the deploy step only; pin wrangler; `permissions: contents: read`; pin actions by SHA. |
| L4 | Low | `detect-careers.yml` puts `${{ inputs.only }}` straight into a shell command. | Pass it through `env:`. |
| L5 | Low | Error handler returns exception text; `/api/meta` returns pipeline errors; `/api/docs` is public. | Generic 500 with a request id; explicit columns; docs off in production. |
| L6 | Low | Python dependencies unpinned (no lock file). | Pin and lock. |
| L7 | Low | The pipeline's HTTP client accepts `file://`/`ftp://` URLs from third-party sitemaps. | Allow only http(s). |
| L8 | Low | No `https?://` check on `jobs.url`; the job pane opens it with `window.open`. | Drop non-http(s) URLs at publish; add a CHECK. |
| L9 | Low | `%` and `_` in the job search aren't escaped. | Reuse the agent's `_like`. |
| I1–I4 | Info | Prompt injection stays inside the victim's own session (no outbound tool); the Hyperdrive id is in the source (against the 2026-11-14 rule); npm: 0 in production; premium tables must not repeat H1, and `/verify` must check the subscription is the caller's. | — |

Not checked (needs live access): Supabase Auth settings (email confirmation, CAPTCHA, redirect
allow-list), drift between the migrations and the live database, Cloudflare zone and WAF settings,
production response headers, Gemini's current data terms, `pip-audit`, repository settings.
