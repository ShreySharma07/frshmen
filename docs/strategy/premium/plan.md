# Plan: Aventra Premium with Razorpay Subscriptions

Written 2026-11-15. Decision in `docs/decisions.md` (same date). Diagram: `architecture.png`
(source `architecture.html`). Sketches of the screens: `docs/wireframes/premium/a-subscription.png`.

Analogy: a gym membership. The front desk (our API) checks your card on every visit; the bank
(Razorpay) takes the fee each month and tells the gym when it went through, failed or stopped.
The gym never takes the member's word for it, and the turnstile isn't a sign on the door.

## 1. What people get

| Free | Premium (₹99 a month, or ₹249 every 3 months) |
|---|---|
| Jobs: list, filters, labels, evidence | Agent: chat, people to ask, email drafts, Send from Gmail, LinkedIn messages |
| Profile, resume, LinkedIn connections upload | Tailored resumes |
| Applications tracker | More fit checks (still a daily cap, for the free Gemini quota) |
| Insights (open question 1) | |
| 3 fit checks a day | |

Both plans renew until cancelled. Cancelling keeps Premium to the end of the period paid for.

## 2. How it works (numbers match the diagram)

1. **Subscribe:** a free person opens a premium section, sees the lock and taps **Get Premium**, then
   picks a plan on `/premium`. The browser calls `POST /api/billing/subscribe {plan}`.
2. **Create:** the API creates a Razorpay subscription on that plan, with our `student_id` in its
   `notes`, and records it as `created`.
3. **Hand back:** the API returns the subscription id and the public key id.
4. **Pay:** the browser loads Razorpay's `checkout.js` (only on `/premium`) and opens the sheet with
   the subscription id. The person approves a UPI Autopay mandate or a card mandate and pays the
   first period.
5. **Verify:** Checkout returns `razorpay_payment_id`, `razorpay_subscription_id` and
   `razorpay_signature`. The browser sends them to `POST /api/billing/verify`.
   - The API checks the signature: HMAC-SHA256 of `payment_id|subscription_id` with the key secret.
   - It re-reads the subscription from Razorpay and saves its status and `current_end`.
   - Premium switches on immediately, without waiting for the webhook.
6. **Webhooks:** Razorpay calls `POST /api/billing/webhook` for every change (`authenticated`,
   `activated`, `charged`, `pending`, `halted`, `cancelled`, `completed`).
   - The API checks the `X-Razorpay-Signature` header: HMAC of the raw body with the webhook secret.
   - It stores each event id once, so a repeated delivery changes nothing.
   - It updates the row.
7. **Save:** `subscriptions.status` and `current_end` are the truth. `is_premium(uid)` reads them.
8. **Gate:** `require_premium` runs before the Agent, tailoring and extra fit checks. Gemini is only
   called after it passes. A free person gets HTTP 402, and the page shows the lock.

### Who counts as premium (`is_premium`)

| Subscription state | Premium? |
|---|---|
| `authenticated`, `active` | Yes |
| `pending` (a renewal failed; Razorpay is retrying) | Yes, until `current_end` + 3 days (open question 2) |
| `cancelled` by the person | Yes, until `current_end` |
| `halted` (retries used up), `completed`, `expired` | No |
| A `premium_grants` row that hasn't ended (you, beta users, set in `/admin`) | Yes |

## 3. Pieces to build

**Database: `db/postgres/0018_billing.sql`**
- **`subscriptions`:**
  - Columns: `student_id`, `razorpay_subscription_id` (unique), `plan` (`monthly` | `quarterly`),
    `status`, `current_start`, `current_end`, `cancel_at_end`, `created_at`, `updated_at`.
  - RLS: a person reads only their own; nobody writes from the browser.
- **`billing_events`:** `event_id` (unique), `type`, `payload` jsonb, `received_at`. API only, never
  readable from the browser.
- **`premium_grants`:** `student_id`, `until`, `reason`. Admin only.
- **`is_premium(uid)`:** one SQL function with the table above. Tested like the other RLS rules.

**API: `api/src/billing.py`**
- **Endpoints:**
  - `subscribe`, `verify`, `cancel` (with `cancel_at_cycle_end`) and `me`, all for the signed-in
    person.
  - `webhook`, with no login and only its signature.
- **`require_premium`:** a dependency added to `/api/agent/chat` and `/api/jobs/{id}/tailor`, and to
  `/api/jobs/{id}/fit` after the free 3.
- **Razorpay calls:** a small `httpx`-style client with basic auth (key id and secret), like the
  Gemini calls.
- **Secrets:** `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET`, set with
  `wrangler secret put`.
- **Vars:** `RAZORPAY_PLAN_MONTHLY`, `RAZORPAY_PLAN_QUARTERLY` and `PREMIUM=on`. Nothing is gated
  until `PREMIUM=on`, so the code can ship before Razorpay is ready.

**Site**
- **`/premium`:** the two plans, the checkout, then a "You're on Premium" state.
- **Locked screens:** Agent, the Tailor button, and fit checks past the free 3. Each shows a short
  preview of what Premium gives and a **Get Premium** button. The sidebar shows a small lock on
  Agent.
- **Settings → Billing:** the plan, the next charge date, Cancel (at period end) and Razorpay's
  receipts.
- **`/admin`:** premium counts and revenue this month, and a "grant Premium" form for beta users.

**Tests**
- RLS tests for the three tables and `is_premium`.
- API tests with signed fake payloads:
  - a bad signature is refused;
  - an event sent twice changes nothing;
  - state changes flip access as in the table;
  - free users get 402 on premium routes;
  - Gemini isn't called for them.
- An end-to-end run in Razorpay test mode before going live.

## 4. Order and estimate (about 5 days)

1. Migration, `is_premium`, RLS tests (½ day)
2. `billing.py`: subscribe, verify, webhook, cancel, me, with tests (1½ days)
3. `require_premium` on the three routes, behind `PREMIUM=on` (½ day)
4. `/premium`, the checkout, locked screens, Billing in settings (wireframes first) (1½ days)
5. Admin counts and grants, then the test-mode run end to end (1 day)

## 5. What only you can do (before going live)

1. **Razorpay account and KYC:** as an individual or unregistered business, with PAN, identity and
   bank details. Razorpay reviews the website.
   - The review usually expects pages for Privacy, Terms, Refunds and cancellation, and Contact.
   - So the privacy and terms work from the launch list comes first.
2. **Switch Subscriptions on** in the dashboard. It may need a request after KYC.
3. **Create two Plans:** ₹99 every 1 month, and ₹249 every 3 months. Send me their ids.
4. **Add the webhook:** URL `https://<site>/api/billing/webhook`, with the subscription events listed
   in section 2. Set a webhook secret.
5. **Put the secrets in the Worker:** the key id and secret, and the webhook secret. Test mode first,
   then the live keys.

## 6. Open questions (my default in brackets)

1. Insights: free or premium? [free: it brings people back]
2. Grace days after a failed renewal? [3]
3. When Premium lapses, saved chats and LinkedIn connections stay but are read-only? [yes, kept
   15 days as now]
4. Refunds? [no partial refunds; cancel stops the next charge. Say so on the Refunds page]
5. Switching monthly ↔ 3 months? [later; at launch, cancel and subscribe again]
6. GST invoices? [Razorpay's receipts until you register for GST]
