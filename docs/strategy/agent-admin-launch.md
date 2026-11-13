# Plan: agent backend, connections, contact lists and the admin dashboard

Written 2026-11-13 for a launch in about two weeks (by ~2026-11-27). Every **Decision** below is
Shrey's; the recommendation is marked. Nothing here is built yet.

Analogy for the whole thing: the agent is a **research assistant with a locked filing cabinet**.
It can read the job board, your résumé and the cabinet (HR and founder lists), and it writes the
letters. It never posts a letter itself, and nobody but you (the admin) can open the cabinet
drawers directly.

---

## 0. What exists today

| Piece | State |
|---|---|
| Job board, filters, bands, categories | Live |
| Accounts (Supabase Auth), profile, résumé upload | Live |
| Fit check (Gemini, 5/day), tailored résumé (2/day) | Live |
| `/agent` page | Shows only those real things; no chat, no outreach |
| Referral outreach | Decided 2026-10-19 (agent drafts, person sends), not built |
| LinkedIn / Gmail / Apollo connections | None |
| Admin pages | None |
| Hosting | API on Cloudflare Python Workers (10 ms CPU per request, waiting on the network is free) |

---

## 1. Agent backend (the core; everything else plugs into it)

**What it does:** a chat on `/agent` (and the command bar) that answers with the person's own
data and calls tools:

| Tool | Reads | Example question |
|---|---|---|
| `search_jobs` | jobs table (band, category, country…) | "Remote backend roles asking 1–3 years" |
| `job_fit` | résumé + one job (existing fit check) | "Am I a fit for this Stripe role?" |
| `find_people` | contact cabinet (§3), YC founders (§4) | "Who should I reach at Razorpay?" |
| `suggest_startups` | YC list + jobs + résumé skills | "Which YC startup suits me?" |
| `draft_outreach` | person + job + résumé | "Write a cold email to this founder" |
| `track` | applications tracker | "Remind me to follow up Friday" |

**How:** one endpoint `POST /api/agent/chat`, streaming. The LLM picks tools; the tools are plain
SQL/Python we already have. Every answer cites what it used (job ids, contact source), same
"evidence" rule as the labels.

**Decision A1: model.** (a) **Gemini Flash free tier (recommended:** already wired, free, has tool
calling; the free tier has a daily request limit shared by everyone, to be checked before build,
so each person gets a daily message cap, ~20 to start) ·
(b) Claude/OpenAI (better tool use, costs money, breaks "free tools only").

**Decision A2: where it runs.** (a) **Same Worker (recommended to start):** LLM calls are waiting
time, not CPU, so 10 ms CPU usually fits; measure in week 1 · (b) a separate free host
(Cloud Run needs a card; Render sleeps) only if (a) fails.

**Guard rails (not optional):** per-user daily cap; the agent never sends anything; contact
details are revealed one person at a time, logged (§3); prompts never include other users' data.

---

## 2. Connections

### 2.1 Gmail: send approved emails
- **Facts (checked 2026-11-13):** putting drafts in the person's Gmail needs `gmail.compose`, a
  *restricted* scope: Google verification **plus a yearly security assessment (~$500)** once past
  100 users. Sending only needs `gmail.send`, a *sensitive* scope: verification, no assessment.
- **Decision B1.** (a) **Draft shown in Aventra, person edits and presses Send, we send with
  `gmail.send` (recommended:** free, keeps "nothing goes out unread") · (b) drafts in Gmail via
  `gmail.compose` (paid assessment after 100 users; fine as a <100-user beta) · (c) "Open in Gmail"
  link with the text prefilled (no Google review at all; works today; weakest UX).
- **Launch note:** Google's verification takes days to weeks. Ship (c) at launch and switch to (a)
  once approved; under 100 test users (a) works unverified.

### 2.2 LinkedIn
- **Facts:** "Sign in with LinkedIn" gives only name, photo, email. Connections and messaging
  APIs are closed to apps like ours; automating them breaks LinkedIn's terms (decided 2026-10-19
  and in `CLAUDE.md`).
- **Plan:** (1) Sign in with LinkedIn (profile + email); (2) the person uploads LinkedIn's own
  `Connections.csv` export (Settings → Data privacy → Get a copy of your data), which the agent
  uses for "who do I know at X"; (3) outreach on LinkedIn = agent writes the note, one tap copies
  it and opens the profile. **No decision needed** unless you want to change 2026-10-19.

### 2.3 Apollo
- **Facts (checked 2026-11-13):** free plan = 900 credits a year (75/month), people search is free
  but returns no emails, revealing an email costs credits, and the licence covers your own sales
  use, not reselling data to users.
- **Decision B2.** (a) **Each person connects their own Apollo key (recommended:** their credits,
  their licence; we store the key encrypted and call Apollo for them) · (b) one Aventra key for
  everyone (75 reveals a month for all users, and against Apollo's licence) · (c) skip Apollo at
  launch; your HR/founder lists (§3, §4) cover the first users.

---

## 3. HR contact list (emails and phone numbers you provide)

This is the riskiest part legally, so it gets the strictest design.

- **Law:** India's DPDP Act covers names, emails and phone numbers. Using them is safe when the
  person made them public themselves (a company careers page, their own LinkedIn) or agreed. A
  bought or scraped list usually isn't. Spam complaints also get the sending Gmail accounts banned.
- **Decision C1: where the list came from.** Please tell me the source of each list. Rows we can't
  explain stay out.
- **Design (recommended):**
  - Stored in a private Supabase table, never in the repo (`CLAUDE.md`: no secrets/PII in git),
    readable only by the API's service role and admins.
  - Each row keeps `source` and `added_at`; a "remove me" email address on the site deletes a row.
  - **Phone numbers are never shown to users** (cold calls from strangers get the list burned);
    emails are shown one person at a time, only inside a drafted outreach, max ~10 reveals a day
    per user, every reveal logged.
  - The agent mostly uses the list to answer *who* ("the campus recruiter at Zoho") and *how*
    (the draft), not to dump contacts.
- **Decision C2.** (a) **as above (recommended)** · (b) emails visible in a searchable directory
  (fast to build, highest risk) · (c) list used only by you, admin-side, not by the agent.

## 4. YC founders list

- Founder names and companies are public on YC's directory; this list is lower risk. Same table
  design as §3 (source, removal), emails revealed the same way.
- The agent joins it with our jobs (YC companies already imported) and the résumé to answer
  "which startup suits me" (skills overlap, stage, hiring now, location) and "reach out to founder X"
  (draft with one specific reason, never a template blast).

---

## 5. Admin dashboard (`/admin`, you only)

| Panel | Source | Effort |
|---|---|---|
| Traffic: visits, top pages, countries | **Cloudflare Web Analytics** (free, no cookies) embedded/linked; sign-ups and active users from Supabase | S |
| Jobs: open count, new today, by source/category/band, boards failing | `meta` snapshot + `runs` table | S |
| Pipeline health: last run, errors, workflows red | `runs` table + GitHub Actions link | S |
| **Add a job by hand** (form like Google Forms: company, title, link, description) | new `manual_jobs` table → a `manual` source in the pipeline, labelled by the same rules | M |
| Bulk upload (CSV of jobs, or the HR/YC lists) | CSV → validate → preview → insert | M |
| Users: count, sign-ups per day, agent usage vs caps | Supabase | S |
| Contact cabinet: rows, sources, removal requests, reveal log | §3 tables | M |

- **Access:** an `is_admin` flag on your account; the API checks it on every `/api/admin/*` call and
  Supabase row-level security blocks the tables for everyone else. The page itself is not linked.
- **Decision D1: Google Forms.** (a) **our own form in `/admin` (recommended:** jobs go straight in,
  labelled) · (b) a real Google Form whose Sheet the pipeline reads (lets others submit without an
  account; needs a Sheets read and spam control).

---

## 6. Two-week order (fits only if the decisions come back in a day or two)

| Days | Build | Done when |
|---|---|---|
| 1–2 | Admin: `is_admin`, `/admin` with jobs, pipeline, users panels; Cloudflare Web Analytics on | You see live numbers |
| 2–3 | Admin: add-a-job form + `manual` source; CSV upload for jobs | A job you add appears labelled in the list |
| 3–4 | Contact cabinet tables + CSV import for HR and YC lists (after C1) | Lists in, private, removable |
| 4–8 | Agent chat: endpoint, tool loop, `search_jobs`, `job_fit`, `suggest_startups`, `find_people`, caps, `/agent` chat UI | Answers cite real jobs/people |
| 8–9 | `draft_outreach` + Gmail "open with text" (B1-c) + LinkedIn copy-and-open; submit Google verification for `gmail.send` | A draft reaches Gmail in two taps |
| 9–10 | LinkedIn sign-in + `Connections.csv` upload | "Who do I know at X" works |
| 10–11 | Apollo per-user key (if B2-a) | Search + reveal with their credits |
| 12–14 | Launch list from the earlier message: landing to `/`, profile for all bands/categories, privacy policy + terms (now must mention contact data), phone test, pipeline alert | Ship |

**Too much for two weeks?** Cut in this order: Apollo → LinkedIn CSV → bulk CSV upload. The
agent chat, admin basics and the legal pages are the launch.

---

## 7. Decisions needed from you

| # | Question | Recommended |
|---|---|---|
| A1 | Agent model | Gemini free tier with per-user caps |
| A2 | Where it runs | Same Worker, measured in week 1 |
| B1 | Gmail | "Open in Gmail" at launch, `gmail.send` after Google verifies |
| B2 | Apollo | Each person's own key |
| C1 | Source of the HR list | (you tell me) |
| C2 | How contacts are used | Agent-only, one reveal at a time, no phone numbers to users |
| D1 | Adding jobs | Own form in `/admin` |

Each answer gets an entry in `docs/decisions.md`.
