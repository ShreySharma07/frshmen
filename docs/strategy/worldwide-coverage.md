# Plan: every job, every country, filtered by each person's preferences (2026-11-11)

Shrey's calls (2026-11-11):

1. Aventra lists **every country**. Someone in Berlin or São Paulo sees local jobs. This replaces
   point 3 of `company-coverage.md` (keep only India, remote and visa/relocation jobs).
2. Aventra fetches **all jobs, every role**, and **each person filters them by their own
   preferences**. This replaces the earlier recommendation in this file to keep tech roles only.

**Analogy.** Today Aventra is a personal shopper: it walks the market with one shopping list
(`config/profile.yaml`) and brings back only what is on it. The new Aventra is a supermarket:
everything is on the shelves with an honest label, and each shopper walks in with their own
list. So the pipeline's job changes from "decide what fits Shrey" to "label every job truthfully",
and deciding what fits moves to the moment a person looks.

Status: a plan. Nothing here is built. Decisions, and the two still open, are in the last section.

## Where we are

| | Now |
|---|---:|
| Companies in `config/companies.yaml` | 703 |
| Careers systems we read | 14 (Ashby 361, Greenhouse 82, Workday 53, Lever 41, others 99) |
| Open jobs stored | ~27k (figure from October; to re-measure) |
| Database used | ~190 MB of 500 MB (figure from 2026-10-19; to re-measure) |

Four things in the code keep the board shaped around one person in India:

1. **One shopping list at fetch time.** `scripts/fetch_jobs.py` runs `match_role(...)` against
   `config/profile.yaml` and stores `role_match` and one of four tech families. Every other
   job is stored without a family, and the API's default list is `role_match` only.
2. **Title screen.** `sources/prefilter.py` drops non-tech titles on Workday and Darwinbox before
   their descriptions are fetched.
3. **India screen.** `india_only` boards keep India and remote jobs only.
4. **English only.** The rules in `extract/` read English. "3 Jahre Berufserfahrung" finds no years.

## Part 1. Label every job, match per person

### What the pipeline stores (facts about the job, the same for everyone)
| Fact | Today | Change |
|---|---|---|
| Years asked, with the evidence line | Yes | None. The precision rule is unchanged |
| **Job family** | 4 tech families, only when it fits Shrey's profile | Every job gets one family from a fixed list, with the title words that decided it; "Other" when no rule is sure |
| Country and city | Yes, India-centred list | Every country (Part 4) |
| Workplace (remote, hybrid, onsite) | Yes | None |
| Visa sponsorship, batch years, pay as written | Yes | None |
| Skills named | Tech skills from `config/skills.yaml` | Same at first; other families get skills later, one catalogue at a time |
| Language of the posting | No | New (Part 4) |

`role_match` and "target roles" leave the pipeline. `config/profile.yaml` stops deciding what is
stored; it becomes Shrey's own preferences, like anyone else's.

### The job-family list
A new `config/job_families.yaml`: about 25 families with title rules, tested on fixtures like the
years rules. A draft, to be pruned by Shrey:

Software engineering · AI and machine learning · Data and analytics · Mobile · DevOps and
infrastructure · Security · QA and testing · Hardware and embedded · Product · Design · Marketing ·
Sales · Customer success and support · Finance and accounting · People and recruiting · Legal ·
Operations and supply chain · Healthcare and life sciences · Research · Education · Content and
writing · Manufacturing and skilled trades · Administration · Other.

Same rule as years: a wrong family is worse than "Other". A job filed under "Other" is still
found by search and by every other filter.

### What each person sets (preferences, kept in their profile)
Years of experience · families (several) · countries and cities · workplace · whether they need
visa sponsorship, and from which country · skills · lowest pay, optional.

The job list opens on these and every one can be changed on the page, as now. Matching is a
database filter at request time, so it has to stay one indexed read: family, country and years
get a combined index, and counts keep coming from the per-run snapshot.

Signed-out visitors see everything, newest first, with the filters open.

## Part 2. The constraint that shapes everything: 500 MB

With the India and tech screens on, the database is already near 40% full. All roles in all
countries is far more: one large Workday company lists thousands of jobs.

| Option | How it works | Holds roughly | Cost |
|---|---|---|---|
| A. Everything in Postgres | No change | ~70k jobs | Full within weeks |
| **B. Card in Postgres, text elsewhere (recommended)** | Postgres keeps what lists and filters need: title, company, family, places, years, evidence line, skills. The stored description moves to Cloudflare R2 (free: 10 GB, 1M writes and 10M reads a month) and loads when a job is opened | ~400k–500k jobs | The API reads R2 for the detail view; search covers title and company, not full text |
| D. Short shelf life | Delete closed jobs after 14 days | Saves 20–30% | Less history for Insights; market trends keep weekly totals, not rows |

Recommended: **B + D**. Option C (tech roles only) is off the table after decision 2.

**The honest ceiling.** Free storage holds a few hundred thousand open jobs, not every job on
earth, which is in the tens of millions. So "all jobs" means all jobs *from the companies we
read*, and the order in which companies are added decides what people find (decision 2 below).
These sizes are estimates until step 0 measures a real row.

## Part 3. Who and how: companies and careers systems

### Find companies in every country
| Source | What it adds | Terms |
|---|---|---|
| **Common Crawl URL index** | Every address it has seen on the careers systems' own hosts (`*.myworkdayjobs.com`, `jobs.lever.co/*`, `*.jobs.personio.de`, `*.teamtailor.com`, `*.recruitee.com`, `*.gupy.io`...). The system and the company's ID are in the address, so no detection is needed | Free, public, built for this use |
| **Wikidata** | Companies by country with their official website (P17, P856), for the detector | CC0 |
| **yc-oss dataset** | Already imported; drop the AI-only filter | Free |
| **Public GitHub lists** | New-grad and remote-job lists per region | Public repos |
| **HN "Who is hiring?"** | Already read | Public API |

Still never used: LinkedIn, Indeed, Glassdoor.

Common Crawl returns tens of thousands of boards. They go into a generated file beside the
curated `config/companies.yaml`, in batches of about 500, each through the existing verify step.

### Careers systems by region
Every new system gets a robots.txt and terms check first, and is skipped if it refuses.

| Region | Systems to add | Notes |
|---|---|---|
| Europe | Personio, Teamtailor, Recruitee, JOIN | All publish a per-company public feed |
| US mid-market | Rippling, Gem, BambooHR, iCIMS, Jobvite | The detector already names the first two |
| Large companies everywhere | SuccessFactors, Phenom, Taleo | Partly covered by `careersite.py` through sitemaps |
| Latin America | Gupy | Brazil's most common system |
| Japan and Korea | HRMOS, Herp, Wanted | Mostly not in English; depends on Part 4 |
| Any own careers site | `careersite.py` (schema.org `JobPosting`) | Works wherever the site has a sitemap |

## Part 4. Make a world of jobs filterable and correct
- **Locations.** Add countries and cities from GeoNames (free, CC BY) so every job gets a country
  code. A job listed in five cities stays one row with five places.
- **Languages.** Detect each posting's language. A language without rules gives **"Not stated"**
  for years and **"Other"** for family, never a guess. Then add rules one language at a time,
  each with fixtures first. Suggested order: German, French, Spanish, Portuguese, Japanese.
- **Visa.** "Abroad with visa" assumes the reader is in India. With a home country in the
  profile it means "outside my country, with sponsorship".

## Part 5. Stay inside the free tiers
| Limit | Today | At world scale | What we do |
|---|---|---|---|
| Supabase 500 MB | ~190 MB | Over, without Part 2 | R2 for text, short shelf life, measured ceiling |
| GitHub Actions | 11–20 min per 3-hourly run | Hours as one job | One job per careers system, in parallel; large boards daily; ETag so an unchanged board costs one request. Free while the repo is public |
| Workers 100k requests a day | Low | Fine for thousands of daily users | Cache list responses at the edge for a minute |
| Hyperdrive 100k queries a day | Low | Same | Same cache |
| Careers hosts | Per-host rate limit in `sources/http.py` | Many more companies on the same hosts | Keep the per-host limit; run time grows, request rate does not |
| Detail requests | Title screen avoids them | Every job's description is needed once | Fetch a description only for a new or changed job (hash of the listing), never per run |

## Latency and scaling (estimates until measured in production)

**Analogy.** Postgres becomes the library's card catalogue and R2 the stacks. Browsing the
catalogue gets faster because the cards are small; fetching one book takes one extra walk.

| Request | Today | With text in R2 |
|---|---|---|
| Job list (20 rows) | 1–2 Postgres queries. Each row also reads its long text to pull the pay line | Same queries on rows a fraction of the size; faster once pay has its own column |
| One job opened | 1 Postgres query | The same query plus one R2 read from inside Cloudflare's network, typically tens of milliseconds. Job text rarely changes, so the response can be cached at the edge |
| Fit check, tailored resume | 1 query, then seconds of Gemini | One extra R2 read; not noticeable next to Gemini |
| Pipeline run | Writes changed rows | Plus one R2 write per new or changed job, 16 in parallel |

What grows with the number of jobs, and the answer to each:

| Pressure | Shows up as | Answer |
|---|---|---|
| Filtered lists (family + country + years) | Slow pages if Postgres has to scan | One combined index for the common filters; the list keeps reading ~20 rows |
| Exact totals ("33 jobs") | Counting reads every matching row: 23 ms at 27k jobs, roughly linear after | Counts from the per-run snapshot; show "1,000+" past a cap |
| Search by title or company | A scan over every row | A trigram index on title and company names; costs storage, so measured first |
| Hyperdrive 100k queries a day | About 50k page views a day at 2 queries each | Cache list responses at the edge for 60 seconds |
| R2 1M writes a month | About 33k new or changed jobs a day | Only changed jobs are written; fine for a few hundred thousand open jobs |
| R2 10M reads a month | About 330k job opens a day | Edge cache on job pages |
| One `jobs.json` and one transaction per run | Memory and run time: the publisher loads every stored job id and the whole fetch at once | Publish per careers system, in batches. **Needed before the screens come off (phase 5)** |
| Fetch time | Hours as one job | One Actions job per careers system, in parallel; large boards daily |

**Where free ends.** Postgres size is the first wall (the measured ceiling goes here once
"Measure storage" has run). The next step up is Supabase's paid tier (8 GB, no pausing) or
splitting jobs across databases; neither is needed for India plus Europe at the sizes expected.

## Phases

| Phase | Work | Gain | Done when |
|---|---|---|---|
| 0 | Measure bytes per job, jobs per company by system, and what the two screens drop today. **Built 2026-11-11:** the "Measure storage" workflow; the fetch log now prints what the India screen drops | A real ceiling | Numbers in this file (waiting for the first run) |
| 1 | Storage: text to R2, slim rows, shelf life. **Built 2026-11-11:** text written to both, backfill, API reads R2 with Postgres as fallback; all off until `docs/setup-r2.md` is followed. **Left:** drop the column (pay column and repost fingerprint first), 14-day shelf life | Room for ~10× the jobs | A job opens from R2 in production |
| 2 | Job families: the list, the rules, fixtures; label every stored job | Every job has a family | Family precision measured on fixtures |
| 3 | Preferences in the profile; the API filters by them; the page opens on them | The board works for any person | Two test profiles see different lists from the same data |
| 4 | Country codes on every job; country filter | Usable outside India | Every stored job has a country |
| 5 | Remove the title screen and the India screen, one careers system at a time, watching size | All jobs from the 703 companies | No `india_only`, no title screen |
| 6 | Common Crawl import for systems we already read | Thousands of companies | First 2,000 verified |
| 7 | India completed, then Europe: adapters, then language rules | The first two regions, each a full board | Per region |

Phases 0–5 need no new source. After them Aventra is a general job board for the companies it
already reads; 6 and 7 are growth.

## Decisions

**Decided (Shrey, 2026-11-11):**
- Every country; all roles, filtered per person.
- **Storage:** slim rows in Postgres, descriptions in Cloudflare R2, closed jobs deleted after
  14 days (options B + D).
- **At the ceiling:** region by region, each finished before the next starts.
- **Region order:** India and Europe first. India means finishing `company-coverage.md` (GCCs,
  Darwinbox, Keka, Zoho Recruit, own careers sites) with the screens off; Europe means Personio,
  Teamtailor, Recruitee and JOIN.
- **Languages:** English first. Other languages are listed with years "Not stated" and family
  "Other" until their rules exist.

**Still open (not blocking phases 0 to 3):**
1. **Family list.** The ~25 above, pruned by Shrey · fewer, broader families. Recommended: the
   ~25; merging later is easy, splitting is a re-label.
2. **Company quality bar for imports.** Everything that verifies · at least one open job.
   Recommended: at least one.
