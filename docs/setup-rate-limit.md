# Setting up the rate-limit rule in Cloudflare (security review M2)

The API has two walls against floods (docs/decisions.md, 2026-11-18):

1. **Outer wall, this page:** a Cloudflare rate-limiting rule. It runs before the Worker, so blocked
   requests don't count against the Workers free plan's 100,000 requests a day.
2. **Inner wall, already in the code:** `api/src/edge.py` with the `API_LIMITER` (120 a minute per
   visitor) and `AI_LIMITER` (10 a minute per visitor, Gemini routes only) bindings in
   `api/wrangler.jsonc`.

The free plan allows one rate-limiting rule. It needs the site on a domain (zone) you added to
Cloudflare. The `*.workers.dev` address has no zone settings, so this waits for the own domain on the
launch list.

## Steps (once the domain is on Cloudflare)

1. Cloudflare dashboard → your domain → **Security** → **Security rules** (older dashboards: **WAF**)
   → **Rate limiting rules** → **Create rule**.
2. Rule name: `API flood`.
3. **If incoming requests match:** Field `URI Path`, Operator `starts with`, Value `/api/`.
4. **With the same characteristics:** `IP` (the free plan's only choice).
5. **When rate exceeds:** `100` requests per `10 seconds` (the free plan's period).
6. **Then take action:** `Block`, for `10 seconds` (the free plan's duration).
7. Deploy.

100 per 10 seconds is far above a person browsing (a page makes a handful of API calls), so only
scripts hit it. To check: `/api/meta` in a loop from one machine should start getting 429s, and the
rule's events show up under Security → Events.
