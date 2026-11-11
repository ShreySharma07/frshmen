# Plan: companies and jobs from every country (2026-11-11)

Shrey's call (2026-11-11): Aventra lists **every country, all jobs**. Someone in Berlin or São
Paulo should see local jobs, not only jobs open to people in India. This replaces point 3 of
`company-coverage.md` ("global companies: keep only India, remote, and visa/relocation jobs").

**Analogy.** Today Aventra is a city library: it buys only the books its own neighbourhood reads.
A world board is a national library, and the hard part of a national library is the shelf space
and the catalogue, not finding books. Most of this plan is about shelves (storage) and the
catalogue (locations and languages); the list of companies is the easy half.

Status: a plan. Nothing here is built. Six choices in the last section are Shrey's to make before
work starts.

## Where we are

| | Now |
|---|---:|
| Companies in `config/companies.yaml` | 703 |
| Careers systems we read | 14 (Ashby 361, Greenhouse 82, Workday 53, Lever 41, others 99) |
| Companies with no system found yet | 67 |
| Open jobs stored | ~27k (figure from October; to re-measure) |
| Database used | ~190 MB of 500 MB (figure from 2026-10-19; to re-measure) |

Two things in the code keep the board India-shaped:

1. `india_only` on the big global boards, plus the location screen in `scripts/fetch_jobs.py`,
   drop non-India jobs before they are stored.
2. The rules in `extract/` read English only. A German posting that says "3 Jahre
   Berufserfahrung" has no years found today.

## The constraint that shapes everything: 500 MB

With the India filter on, the database is already near 40% full. Workday tenants of large
companies list thousands of jobs each, so turning the filter off for the 703 companies we
already have would pass 500 MB before a single new company is added. Storage is decided first
(decision 1 below); the rest of the plan assumes option B.

| Option | How it works | Fits roughly | Cost |
|---|---|---|---|
| A. Keep everything in Postgres | No change | ~70k jobs | Full within weeks |
| **B. Card in Postgres, text in object storage (recommended)** | Postgres keeps what the list and filters need (title, company, location, years, evidence line, skills). The three stored sections move to Cloudflare R2 (free: 10 GB, 1M writes and 10M reads a month) and load when a job is opened | ~400k–500k jobs | The API reads R2 for the detail view; one more moving part |
| C. Tech roles only | Keep the current title screen (`sources/prefilter.py`) for every board, so sales, retail and operations jobs are never stored | Cuts volume to perhaps a quarter | "All jobs" becomes "all tech jobs" |
| D. Short shelf life | Delete closed jobs after 14 days instead of keeping them | Saves 20–30% | Less history for Insights |

B and C combine. My recommendation is B + C + D: every country, tech and data roles, text in R2.
The row-size numbers above are estimates; step 0 measures them.

## The plan, in five layers

### 0. Measure (half a day)
Average bytes per job row and per index, jobs per company by careers system, and how many jobs
the India screen drops per run today. That one number says how many jobs "everything" is.

### 1. Open the tap we already have (largest gain, no new source)
- Replace `india_only` with a per-company `regions` setting that defaults to all.
- Remove the India screen for one careers system at a time, smallest first (Greenhouse, Lever,
  Ashby), watching database size after each. Workday last.
- Check: jobs stored per country before and after; fetch run stays under 90 minutes.

### 2. Who: find companies in every country
| Source | What it adds | Terms |
|---|---|---|
| **Common Crawl URL index** | Every address it has seen on the careers systems' own hosts (`*.myworkdayjobs.com`, `jobs.lever.co/*`, `*.jobs.personio.de`, `*.teamtailor.com`, `*.recruitee.com`, `*.gupy.io`...). The system and the company's ID are in the address, so no detection is needed. This was phase C of the India plan with an India filter; without the filter it is the main source | Free, public, built for this use |
| **Wikidata** | Companies by country with their official website (P17, P856), to feed the detector for countries Common Crawl covers thinly | CC0 |
| **yc-oss dataset** | Already imported; drop the AI-only filter | Free |
| **Public GitHub lists** | New-grad and remote-job lists maintained per region | Public repos |
| **HN "Who is hiring?"** | Already read | Public API |

Still never used: LinkedIn, Indeed, Glassdoor.

Common Crawl will return tens of thousands of boards. Add them in batches of about 500, each
batch going through the existing verify step, so one bad batch can be undone.

### 3. How: careers systems by region
The 14 systems we read are strong in the US and India. Other regions run on systems we don't
read yet. Order by how many companies each unlocks; every one gets a robots.txt and terms check
before an adapter is written, and is skipped if it refuses.

| Region | Systems to add | Notes |
|---|---|---|
| Europe | Personio, Teamtailor, Recruitee, JOIN | All publish a per-company public feed; Personio's is XML |
| US mid-market | Rippling, Gem, BambooHR, iCIMS, Jobvite | The detector already names the first two |
| Large companies everywhere | SuccessFactors, Phenom, Taleo | Partly covered by `careersite.py` through sitemaps |
| Latin America | Gupy | Brazil's most common system |
| Japan and Korea | HRMOS, Herp, Wanted | Postings mostly not in English; depends on layer 4 |
| Any own careers site | `careersite.py` (schema.org `JobPosting`) | Already works wherever the site has a sitemap |

### 4. Catalogue: make a world of jobs filterable and correct
- **Locations.** `config/locations.yaml` is India-centred. Add countries and cities from
  GeoNames (free, CC BY) so every job gets a country code. One job listed in five cities stays
  one row with five places.
- **Languages.** Detect each posting's language. A language without rules gives **"Not stated"**,
  never fresher: the precision rule holds everywhere. Then add years-of-experience rules one
  language at a time, each with its own fixtures in `tests/fixtures/` before any rule ships.
  Suggested order: German, French, Spanish, Portuguese, then Japanese.
- **Visa.** "Abroad with visa" assumes the reader is in India. The profile needs a home country
  so the filter means "outside my country, with sponsorship".
- **The page.** Country as the first location filter, set from the profile; the API query gets
  an index on country so the list stays one indexed read.

### 5. Keep: free-tier budget at world scale
| Limit | Today | At world scale | What we do |
|---|---|---|---|
| Supabase 500 MB | ~190 MB | Over, without layer 0 and decision 1 | R2 for text, tech roles only, short shelf life |
| GitHub Actions | 11–20 min per 3-hourly run | Hours if run as one job | Split by careers system into parallel jobs; big boards daily; ETag so unchanged boards cost one request. Free while the repo is public |
| Workers 100k requests a day | Low | Fine for thousands of daily users | Cache list responses at the edge for a minute |
| Hyperdrive 100k queries a day | Low | Same | Same cache |
| Careers hosts | Per-host rate limit in `sources/http.py` | 50× the companies on the same hosts | Keep the per-host limit; total run time grows instead of request rate |

## Phases

| Phase | Work | Gain | Done when |
|---|---|---|---|
| 0 | Measure; decide storage | A real ceiling | Numbers in this file |
| 1 | Storage change (R2 or chosen option) | Room for ~10× the jobs | A job opens from R2 in production |
| 2 | Country codes on every job; country filter on the page | The board is usable outside India | Every stored job has a country |
| 3 | Remove the India screen, system by system | 3–5× the jobs from the companies we have | No `india_only` left |
| 4 | Common Crawl import for systems we already read | Thousands of companies, mostly US and Europe | First 2,000 verified |
| 5 | Europe adapters (Personio, Teamtailor, Recruitee, JOIN) | Germany, Nordics, Netherlands, France | Fixtures pass; boards fetched |
| 6 | German and French years rules | Labels on those jobs, not "Not stated" | Fresher precision on new fixtures does not drop |
| 7 | Further regions and languages, one at a time | Latin America, Japan, the Gulf, Southeast Asia | Per region |

Phases 0–3 need no new source and make the board global for the companies already listed.

## Decisions for Shrey

1. **Storage:** A, B, C, D or a mix. Recommended: B + C + D.
2. **"All jobs":** every role, or tech and data roles in every country? Recommended: tech and
   data. Aventra's labels and skills are built for them, and it is a quarter of the volume.
3. **First region after the US:** Europe, Southeast Asia or the Gulf. Recommended: Europe, since
   its systems publish clean feeds and many roles there sponsor visas.
4. **Languages:** English only at first, with other languages shown as "Not stated", or rules
   for German and French before Europe launches. Recommended: English first.
5. **Company quality bar:** Common Crawl includes tiny and dead companies. Add everything that
   verifies, or only boards with at least one open tech job. Recommended: at least one.
6. **The curated list:** keep `config/companies.yaml` hand-reviewed and put imported companies in
   a second, generated file. Recommended: yes, so reviews of the curated file stay readable.
