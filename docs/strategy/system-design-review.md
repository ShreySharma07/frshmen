# System design review (2026-11-18)

What Aventra uses today, what it is missing, and what is worth adding before launch (~2026-11-27).
Scale assumed: hundreds to a few thousand people, on free tiers (Cloudflare Workers 100k requests
and 100k Hyperdrive queries a day, 10 ms CPU per request; Supabase 500 MB, pauses after a week idle;
Gemini free tier). Security has its own section, written by a separate review.

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
