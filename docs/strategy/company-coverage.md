# Strategy: cover every company that hires in India (2026-10-18)

**Goal:** list every open target-role job at any company that hires engineers in India or
remotely, including companies that post on their **own careers site** rather than a shared
job board. Shrey asked for this on 2026-10-18 ("many US companies have India offices and hire
here but have their own career pages; we need to keep them too").

**Analogy:** a census. First you need the list of households (which companies exist), then each
household's address (where its careers page lives and what system runs it), then someone who can
read that kind of door sign (an adapter per careers system). Missing any of the three loses the
household. Today we only knock on doors whose address we already wrote down by hand.

## Where we are

| | Count |
|---|---:|
| Companies in `config/companies.yaml` | 612 |
| Fetched (board verified) | 375 |
| Not found on Greenhouse / Lever / Ashby / SmartRecruiters, even under name variants | 237 |
| Of those, Indian companies on Darwinbox that refuse GitHub's runners (HTTP 403) | 19 |
| Headquarters: US / India / other | 382 / 111 / 119 |
| Open jobs in the database | ~27k |

The 237 are mostly companies on their own careers site or on a system we can't detect from the
company name (Workday, SuccessFactors, iCIMS, Phenom...). Big names among them: Google
DeepMind, Fireworks AI, Replicate.

For scale: India has **1,700+ global capability centres** (foreign companies' own offices here;
Nasscom, FY2024; the Zinnov–Nasscom 2026 report counts 2,117). Most of them recruit through the
parent company's careers site, usually on Workday, SuccessFactors, Oracle, iCIMS or Phenom.

## The plan: four layers

### 1. Who: build the company list from open sources

| Source | What it adds | Cost / terms |
|---|---|---|
| **Common Crawl URL index** (free, public copy of the web) | Every `*.myworkdayjobs.com`, `jobs.lever.co/*`, `jobs.ashbyhq.com/*`, `boards.greenhouse.io/*`, `*.darwinbox.in`, `*.successfactors.com` and similar address it has seen. Thousands of companies, including MNCs, with the careers system already known. | Free; made for this kind of use; runs in GitHub Actions |
| **GCC lists** (public articles listing India GCCs; Nasscom/Zinnov press releases) | The foreign companies with Indian engineering offices, i.e. exactly the ones you asked about | Free to read; small manual curation, no scraping of paywalled reports |
| **yc-oss dataset** (already used) | YC startups, now with their **website** so careers pages can be found | Free (already in `scripts/import_yc.py`) |
| **Wikidata** (open database, CC0) | Official website of known companies (property P856), to find their careers page | Free public query API |
| **GitHub new-grad lists** (e.g. SimplifyJobs) | Companies hiring entry-level right now, with application links that reveal the careers system | Public repos; read through GitHub |
| **HN "Who is hiring?"** (already used) | Startups' board links | Already in discovery |

Never used, per `CLAUDE.md`: LinkedIn, Indeed, Glassdoor.

### 2. Where: find each company's careers system automatically

A new **detector** takes a company's website, finds its careers page (`/careers`, `/jobs`, or the
link labelled "Careers"), and recognises the system behind it from links and embeds:

- `boards.greenhouse.io/embed/job_board?for=X` → Greenhouse `X`
- `jobs.lever.co/X`, `jobs.ashbyhq.com/X`, `apply.workable.com/X` → those boards
- `X.wdN.myworkdayjobs.com/Site` → Workday tenant/site
- `career*.successfactors.*`, `*.oraclecloud.com/hcmUI/CandidateExperience`, `*.icims.com`,
  `*.phenompeople.com`, `*.eightfold.ai`, `*.darwinbox.in`, `*.keka.com`, `zohorecruit`, ...

If nothing is recognised, the **generic reader** takes over (next layer). The detector fills
`ats` and `slug` in `companies.yaml`, so the existing verify-and-fetch flow just works. Detection
runs weekly in GitHub Actions; this sandbox can't reach those sites.

### 3. How: read the jobs

- **Systems we already read:** Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday,
  Eightfold, Oracle, Darwinbox, Keka, Zoho Recruit, and company sites with schema.org data
  (`sources/careersite.py`).
- **Systems to add, by expected India coverage:** SuccessFactors (common at MNC GCCs; partly
  covered by the careersite reader), Phenom, iCIMS, Taleo, then smaller ones (Freshteam,
  Recruitee, Teamtailor, Personio, Jobvite, BambooHR).
- **Generic fallback for any own careers site:** Google only lists a job in Google Search if the
  page carries schema.org `JobPosting` data. So most careers sites publish exactly the fields we
  need (title, location, date, full description) in a standard format, and `careersite.py`
  already reads it through the sitemap. Sites without a sitemap or that render jobs only in the
  browser can't be read this way. Those need an adapter, or we skip them.
- **Darwinbox** refuses GitHub's runners (HTTP 403). We respect that, and don't try to get
  around the block. Those 19 companies need either an approved route or a different source.

### 4. Keep: stay inside the free tiers

- **What to fetch:** MNC tenants list thousands of global jobs. Filter by location and title
  *before* fetching each job's detail page (the `sources/prefilter.py` pattern), and keep only
  India, remote, and visa/relocation jobs.
- **Database (500 MB, ~190 MB used):** store only three sections per job (About the role, Required,
  Preferred), not the whole description; extractors read the full text first.
- **Run time:** the 3-hourly fetch takes 11–20 minutes now (90-minute limit). Big careers
  systems change slowly: fetch them daily instead of every 3 hours, using ETag caching and
  per-host rate limits (already in `sources/http.py`). Done 2026-10-19: the `india_only` boards
  are read by the 03:17 UTC run only (`fetch_jobs.py --skip-global` on the others).
- **GitHub Actions minutes:** free for public repositories. Keep the repo public, or budget
  around 2,000 minutes a month.

## Phases

| Phase | Work | Expected gain |
|---|---|---|
| **A (now)** | Re-check the 237 (running); add `website` to companies; build the detector; run it on the 237 | +50–150 companies, several big labs and Indian firms |
| **B** | GCC list + Wikidata websites → detector | The India offices of foreign companies: hundreds |
| **C** | Common Crawl ATS index → detector-free (the system is in the URL) → India filter | Thousands of companies, mostly via Workday / SuccessFactors |
| **D** | New adapters: SuccessFactors, Phenom, iCIMS, Taleo | Unlocks the MNC sites B and C find |
| **E** | GitHub new-grad lists | Entry-level-heavy companies, mostly US |

## Progress

- **A (2026-10-18):** detector run on 229 of the 236 unverified companies; verified boards went
  from 376 to 407. A spot check of 14 where nothing was recognised found Gem, own-site job pages
  with no hiring system, pages that only render in the browser, and LinkedIn-only hiring; no
  single missing system. The detector now names Gem, Rippling, Dover, Wellfound, Breezy, JazzHR
  and YC job pages, and re-reads "not found" companies when it learns a new one.
- **Found on the way:** Workable and SmartRecruiters boards were verified but never fetched (no
  adapter); 18 companies including PhonePe, Swiggy and Freshworks. Both fetchers added.
- **B (started 2026-10-18):** 91 global capability centres (banks, chip makers, industrials,
  pharma, consulting) added with their website and `india_only`; detection finds their systems.

- **B results (2026-10-18):** 15 of the 91 GCCs verified (Workday 12, Oracle 3). Of the rest:
  iCIMS 5, SuccessFactors 3, Taleo 2, Phenom 2, and 62 not found (mostly pages rendered in the
  browser, or the company's own system).
- **D, first step (2026-10-19, Shrey):** before writing adapters, sites on SuccessFactors, Phenom
  or iCIMS are tried with `careersite.py` through their job sitemap (Arm and Moody's publish
  one with schema.org job pages). Taleo is left for later.
- **Storage (2026-10-19):** descriptions are stored as About the role / Required / Preferred
  (`extract/stored_text.py`), after extraction has read the full text; the YoE line behind each
  label is always kept. On 455 stored jobs: 37% of the text kept, no label changed when
  re-classified from the stored text. Older rows are rewritten once by
  `scripts/compact_descriptions.py` (workflow "Compact stored descriptions").

## Decided (Shrey, 2026-10-18)

1. **Order:** A → B → D → C → E.
2. **Storage:** keep only About the role, Required and Preferred skills for every job (Shrey's
   option). Extractors still read the full text first and keep their evidence.
3. **Global companies:** keep only India, remote, and visa/relocation jobs.

See `docs/decisions.md` (2026-10-18).
