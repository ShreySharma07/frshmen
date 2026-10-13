# frshmen: from personal board to a product for students

Written 2026-10-09. A plan, not a decision log: each choice marked **Decision** goes to Shrey
(options + recommendation), and the chosen option is then logged in `docs/decisions.md`.

Analogy for the whole plan: opening a dhaba. First the food must taste good and the place must
look inviting (UI). Then regulars must come back on their own (alerts, retention). Then word of
mouth spreads to the next college (distribution). Only then do you charge for extras
(monetization). Charging before people come back is how most of these die.

---

## 0. How we work: Shrey learns every step

The point is that Shrey can build and run this himself, not just own it.

- **Each phase has a "What you'll learn" list.** Before building, Claude explains the concept with
  a short analogy, then Shrey attempts the design or the code first.
- **Hints come only after Shrey has struggled a couple of times.** Claude gives a hint, then a
  bigger hint, and only then the answer.
- **Claude reviews Shrey's work like a senior engineer:** what breaks, why, and what to read next.
- **Each phase ends with a short write-up by Shrey** (`docs/learning/phase-N.md`): what was built,
  what went wrong, and what he'd do differently. These double as portfolio material and interview
  stories.
- **Gate for moving on:** Shrey can explain each piece he built without notes.

---

## 1. Things that change once it isn't just for Shrey

These must be settled before or during Phase 1.

1. **Personal settings are hard-coded.** "My target roles", "Only where I can work", and the
   2026-batch rules come from `config/profile.yaml`. Every student needs their own: batch year,
   roles, cities, visa needs.
2. **The free-only rule will bend.** Expect, roughly in this order:
   - a domain (~₹800/yr)
   - an email-sending service
   - Cloudflare Workers Paid ($5/mo) once traffic grows
   - payment-gateway fees

   **Decision:** budget, and when each step happens.
3. **Terms of service for commercial use.** Reading public job boards for personal use is easy to
   defend. Republishing them in a paid product is not the same for every source.
   - Before charging money, review each source's terms.
   - Keep linking out to the employer's own "Apply" page.
   - Drop any source that forbids reuse.
   - LinkedIn, Indeed and Glassdoor stay off-limits (`CLAUDE.md`).
4. **Data protection (India's DPDP Act, 2023).** Storing students' emails, resumes, skills or
   contacts needs:
   - clear consent
   - a stated purpose for each piece of data
   - a way to delete it
   - a privacy policy

   This applies most to sections 6 and 7 below.
5. **Who runs it.** **Decision:** stay a side project, or register a company. A company is needed
   for payments (Razorpay), GST past the revenue threshold, and signing college contracts.

---

## 2. Phase 1: UI for everyone (2–3 weeks)

**Goal:** a stranger opens the link, understands the site in 5 seconds, and finds 5 relevant jobs
in under a minute.

- **Onboarding without login.**
  - On the first visit the student picks a batch (2025/2026/2027), roles, cities, and whether they
    need a visa.
  - The choices are saved in the browser.
  - Filters and labels adapt to them ("Fits you" replaces "My target roles").
- **Name, brand and landing.**
  - A one-line pitch, e.g. "Fresher jobs from 600+ company career pages, checked for hidden
    '2+ years' traps".
  - A live job count.
  - The evidence highlight as the selling point.
- **Mobile first.** Most visits will come from WhatsApp links.
  - Sticky filters.
  - Cards readable while scrolling with one thumb.
  - A quick view that opens without losing your place in the list.
- **Habit features.**
  - "New since your last visit" badges.
  - Saved and applied markers per job (in the browser for now).
  - Shareable filtered links, e.g. `?batch=2026&role=ml&city=Bengaluru`.
- **A page per job.** Each job gets its own URL, with a preview card when shared on WhatsApp or
  LinkedIn.
- **Trust.** A "Report wrong label" button.
  - Each report becomes a labelled fixture (`tests/fixtures/labeled/`), which keeps the fresher
    precision honest.
  - Reports are reviewed by Shrey, never applied automatically.
- **Analytics:** Cloudflare Web Analytics (free, no cookies).

**Exit gate:** 50 real students use it, and at least 30% return within a week.

**What you'll learn:**
- React state that lives in the URL and in localStorage
- Responsive CSS and mobile-first layout
- Open Graph preview tags
- Basic product analytics (activation, retention)
- How to run a 5-person usability test

---

## 3. Phase 2: Accounts and alerts (2–3 weeks)

**Goal:** students come back without having to remember the site.

- **Optional sign-in** by email magic link.
  - **Decision:** which auth provider (options with free tiers, compared then).
- Preferences, saved jobs and applied markers sync across devices.
- **Alerts for new matches.**
  - Daily email digest.
  - Instant alerts through a Telegram bot (free).
  - WhatsApp is paid per message, so later.
- **Gemini "Check my fit"** (already built, off) switches on for signed-in users only, with a
  daily cap per user. This answers the open "who may use it" question.

**Exit gate:** 500 sign-ups, and at least 40% of alert recipients open them weekly.

**What you'll learn:**
- Authentication: sessions, magic links, and why we don't store passwords
- Schema changes and D1 migrations
- Background jobs and email deliverability
- Rate limiting
- DPDP consent basics

---

## 4. Phase 3: Scale the plumbing (in parallel, 1–2 weeks)

- **A custom domain**, which unlocks edge caching. Cached lists stretch D1's 5M reads/day much
  further.
- **Watch the free-tier ceilings and decide paid thresholds in advance:**
  - Workers: 100k requests/day
  - D1: 5M rows read/day, 100k rows written/day
  - GitHub Actions minutes
- **More sources:**
  - GitHub new-grad and internship lists
  - Adzuna India API
  - Google Sheets lists
  - The admin-only "Paste a job link" box (future scope since 2026-10-08)

**What you'll learn:**
- Caching (what to cache, for how long, and how to invalidate)
- Reading usage dashboards
- Capacity planning on free tiers

---

## 5. Phase 4: Spread across colleges (ongoing; starts during Phase 1)

- **Seed at home first.** Shrey's own college and batch: WhatsApp groups and placement
  coordinators. Fix what they complain about before going wider.
- **Campus ambassadors.** One student per college, 10–20 colleges to start.
  - Each gets a referral link and a leaderboard.
  - Perks: premium features, certificates, LinkedIn shout-outs.
- **College pages.** `/c/<college>`: the same board, pre-filtered, with the college's leaderboard.
  Easy to drop into that college's groups. Section 6 grows these into a full university group.
- **Content loop.** A weekly "Top 10 fresher AI/ML jobs this week" post on LinkedIn, X and
  Telegram, generated from the data.
- **Placement cells (TPOs).** A free weekly digest for their students, which warms them up for
  the paid college plan.

**Metrics:**
- weekly active users per college
- "Apply" clicks, our proxy for value delivered
- referral conversions

**What you'll learn:**
- Growth loops and referral mechanics
- Writing for students
- Running a small ambassador program
- Talking to placement officers

---

## 6. University groups: see who's doing what (Shrey's idea)

**What it is:** a private space per university where students can see:
- what skills their peers are building
- how many students from their college applied to each job

**Why it works:** peer signal. "12 people from my college applied here" and "3 seniors know
PyTorch and got shortlisted" are things no other job board shows.

### How it works
- **Joining.** Students join their university group by verifying a college email (`@college.edu`
  or the college's domain) or through an ambassador invite code.
  - **Decision:** which, or both.
- **Skill profiles (opt-in).**
  - Students list skills (picked from a fixed list, e.g. Python, PyTorch, React, DSA level),
    projects, and what they're learning now.
  - They choose who sees it: the group or only themselves.
- **"Applied" counter per job.**
  - When a student marks a job "Applied", the job card shows "N from your university applied".
  - Students can also mark "Got interview" and "Got offer". These give the group a real-time view
    of which companies actually respond.
- **Group views.**
  - Skill heatmap of the batch.
  - Trending companies the group is applying to.
  - "Students who applied here also applied to…".

### Privacy rules (non-negotiable)
- **Opt-in, consent recorded, deletable** (DPDP).
- **Counts only, never names, on applications.**
- **Small counts are hidden.** Show "fewer than 3" instead of the exact number, so nobody can be
  singled out.
- **Skills are visible by name only if the student chooses.** The default is anonymous aggregate.
- **Nothing from a group is ever shown to other colleges or to employers** without a separate,
  explicit consent.

**What you'll learn:**
- Multi-tenant data design (one app, many universities)
- Role-based access
- Privacy-preserving aggregates (k-anonymity in plain terms)
- Consent flows

---

## 7. Referral helper: who in my network can refer me? (Shrey's idea)

**What it is:** for any job, an AI agent finds the most relevant people in the student's own
LinkedIn network to ask for a referral, and prepares a message the student wrote or approved.

### The hard constraint, and the design that respects it
LinkedIn's User Agreement forbids:
- automated scraping of LinkedIn
- bots that send messages or connection requests

`CLAUDE.md` also bans scraping LinkedIn. Breaking this gets the student's account restricted,
and exposes us to legal risk. So the agent never logs into LinkedIn, never scrapes it, and never
sends anything. The student stays the sender.

### Compliant flow
1. **The student imports their own network.** LinkedIn's "Get a copy of your data" gives every
   user a `Connections.csv` (name, company, position, connected-on date, and email if the contact
   shared it).
   - The student uploads it.
   - It's stored only for them, deletable anytime.
   - It's refreshed when they upload again.
2. **Matching for a job.** The agent ranks connections:
   - current company equals the job's company first
   - then same team or function words in their title
   - then seniority that typically refers (engineers and managers over recruiters, or recruiters
     as a fallback)
   - then how recently they connected

   Each match comes with a one-line "why".
3. **Message drafting.**
   - The student writes their template once (tone, a short pitch, resume link).
   - The agent fills in the person's name, the role, the job link, and one specific line about why
     the student fits, using the fit-check output.
   - The student edits and approves every message.
4. **Sending stays manual.** One tap copies the message and opens that person's LinkedIn profile
   (or a mailto, if an email was shared). The student pastes and sends it themselves.
5. **Tracking.**
   - The student marks "asked", "referred" or "no reply".
   - The agent suggests a polite follow-up after N days. The student still sends it.

### Optional later
- University-group cross-matching: "a senior from your college works there", only with that
  senior's opt-in.

**Guardrails:**
- A per-day cap on drafted asks, so referrals don't turn into spam.
- No message is sent without the student's action.
- Uploaded contacts are never shared with anyone, including the university group.

**What you'll learn:**
- Building an LLM agent with tools (ranking, retrieval, drafting)
- Prompt design with user-written templates
- Evaluating an agent's suggestions
- Handling other people's personal data responsibly
- Reading a platform's terms before building on it

---

## 8. Phase 5: Monetization (after roughly 2–5k weekly active users)

| Option | Who pays | Price idea | Tradeoff |
|---|---|---|---|
| **A. Freemium Pro** (recommended first) | Students | ₹49–99/month | Features: instant alerts, unlimited AI fit checks, the referral helper (section 7), resume-to-job tailoring tips, an application tracker. Simple to build; needs volume, since students pay little |
| **B. College plan** | Placement cells | ₹10–50k per college per year | Features: the university group dashboards (section 6, aggregate only), branded digests, eligibility exports. Bigger cheques, slow sales cycles |
| **C. Employer listings** | Startups hiring freshers | ₹1–5k per featured post | Needs traffic first; must be clearly labelled "Sponsored" so it doesn't erode trust in the labels |
| D. Ads / course affiliates | Advertisers | low | Easy, but cheapens the brand; not recommended early |

- **Payments:** Razorpay (needs a business identity; GST registration past the threshold).
- **Free stays free.** Browsing every job and its evidence stays free; that's the growth engine.

**What you'll learn:**
- Pricing experiments
- Payment integration and webhooks
- Subscription state
- Unit economics (cost per active user vs revenue per user)

---

## 9. Order of work

1. Phase 1: UI for everyone
2. Seed at Shrey's college (Phase 4 starts)
3. Phase 2: accounts and alerts
4. University groups (section 6), starting with the "Applied" counter
5. Phase 3 scaling, as limits approach
6. Referral helper (section 7), first as a Pro feature
7. Phase 5 monetization, once weekly retention holds

---

## 10. Open decisions for Shrey

1. **Product name and domain:** keep "frshmen" or rebrand?
2. **Audience scope:** AI/ML and Python freshers only, or all tech fresher roles (SDE, data,
   analyst)? Wider means more users, but a weaker "precise for AI/ML" pitch.
3. **Budget:** OK to spend on a domain now? Roughly how much per month later?
4. **Side project or company?** (Affects payments, GST, terms, college contracts.)
5. **University verification:** college email, invite code, or both?
6. **Referral helper:** confirm the compliant design (CSV import, manual send). No LinkedIn
   automation, ever.
