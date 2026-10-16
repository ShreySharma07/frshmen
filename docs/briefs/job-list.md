# Brief: the job list (M4.3)

Kario's main screen. Step 1 of the UI process in `CLAUDE.md`: what the screen is for, the one
thing the user must do, real content, and products whose *patterns* we borrow (never their look).
Shrey reviews this before the wireframe (M4.4).

## Who it's for
Students and engineers in India at every experience level, freshers included (decided
2026-10-16). Most are on budget Android phones on patchy 4G, checking between
classes or on a commute. They come back every few days to ask "anything new for me?"

## What the screen is for
Show every open job that fits **my years of experience** and my roles, newest first, and let me
trust each label at a glance.

## The one thing the user must do
**Open a job that fits them.** Everything else (filters, sorting, saving) only serves that.

## What each card must answer, in priority order
1. **Can I apply with my experience?** The years asked ("0–1 yrs", "3+ yrs", "Not stated") and
   the exact snippet behind it, one tap away. This is what Kario is for; it must be the
   loudest thing after the title.
2. **What and where:** title, company, city or Remote/Hybrid/Onsite.
3. **How fresh:** "2 days ago", plus a "New" mark for jobs since my last visit.
4. **Extras when present:** visa sponsorship, internship → full-time conversion, batch years
   ("2026 batch").

Description text never appears on the list; it's on the job page.

## Filters
- **My experience** (new): 0 / 1 / 2 / 3–5 / 5+ years. A job shows when its minimum is at or
  below my years. Jobs that state no years show with a "Not stated" tag, never as entry-level.
  The precision rule stays: a "3+ years" job never shows to someone who picked 0–2 years.
- Role (AI/ML, Backend, Mobile), location (India city / Remote / abroad with visa), internship.
- Each option shows its live count, so empty results are avoided before the tap.

## States to design
- **Loading:** the skeleton of the first 5 cards, no spinner.
- **Empty:** says which filter removed the most jobs and offers to drop it.
- **Error / offline:** the last list seen stays visible with "Couldn't refresh" and a retry.
- **New since last visit:** a divider line, "Seen up to here".

## Real content samples
From the pipeline's local snapshot (2026-10-06, 455 open jobs from 7 companies; the live site
has ~27k). Used verbatim in the wireframe; no lorem ipsum.

| Title | Company | Where | Years | Evidence snippet |
|---|---|---|---|---|
| Software Engineer – New Grad | Scale AI | San Francisco, CA | 0 (new grad) | "New Grad" in the title |
| ML Research Engineer, ML Systems | Scale AI | SF; Seattle; New York | Not stated | (none) |
| Backend Engineer, Chanakya | Sarvam AI | Bengaluru, onsite | 3–6 | "3–6 years in backend engineering with production systems in continuous operation" |
| ML Engineer (Data), Foundational Models | Sarvam AI | Bengaluru, onsite | 3+ | "3+ years of experience building large-scale data systems" |
| Senior/Staff ML Research Engineer, General Agents | Scale AI | SF; New York | 5+ | "5+ years of experience building and deploying machine learning or AI systems" |

These show the hard cases: long titles, multiple cities, missing years, and long evidence.

## References (pattern to borrow, not the look)
| Product | Pattern we borrow | Why it fits |
|---|---|---|
| **Google Flights** results | Filter chips at the top with counts. Each row shows the 3 numbers you compare (price, time, stops) in fixed columns. | Our "years / where / when" is the same quick comparison down a list. |
| **Linear** issue list | Dense rows that stay readable, and a filter bar that reads as a sentence ("Experience ≤ 2 yrs · AI/ML · India"). | A long list that people scan daily; the filters stay visible and easy to undo. |
| **Welcome to the Jungle (ex-Otta)** job cards | A "why this matches you" line on each card. | Maps onto our evidence snippet: the reason the label was given, shown up front. |

## Constraints
- 390 px first; it must also work at 1280 px.
- Performance budget from `CLAUDE.md`: LCP < 2.5 s on Fast 4G, < ~170 KB JS, INP < 200 ms.
- No motion on the list except what explains a change (a filter result count updating, the new
  items divider).

## Decided by Shrey (2026-10-16)
1. **"My experience" is asked once** on the first visit and remembered; it can be changed later
   from the filter bar.
2. **The evidence snippet sits behind a tap** on phones, so cards stay short.
3. **"Not stated" jobs show by default**, with their tag.
