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
| Insights | |
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
| `pending` (a renewal failed; Razorpay is retrying) | Yes, until `current_end`; no grace days (Shrey) |
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

## 6. Answers (Shrey, 2026-11-16)

1. **Insights** stays free.
2. **No grace days.** A failed renewal keeps Premium only until the end of the period already paid
   for.
3. **When Premium lapses**, saved chats and LinkedIn connections stay readable but can't be
   continued. The agent stays locked until the person renews.
4. **No refunds.** Cancelling before the period ends stops the next charge. The Refunds page says
   so.
5. **Switching between monthly and 3 months** comes later. At launch: cancel, then subscribe again.
6. **Invoices:** Razorpay's receipts.

## 7. Edge cases and how each is handled

✅ = covered by the design above. ➕ = added because of this list. ★ = must work before launch.

**Paying**
1. ✅ Pays, then closes the tab before we hear back: the webhook switches Premium on anyway.
2. ✅ The webhook and the verify call arrive in either order: both write from Razorpay's own data.
3. ➕★ Double-clicks Subscribe, or opens two tabs: an unfinished (`created`) subscription is reused,
   so nobody is charged twice.
4. ➕ Abandons the checkout: `created` never counts as premium; such rows are deleted after a day.
5. ➕ Already premium and opens `/premium`: show "You're on Premium until …", not the checkout.
6. ➕ The UPI app or bank declines the mandate: no charge, no access, and the message "Try a card or
   another UPI app".
7. ✅➕ Paid while our API was down: Razorpay retries webhooks and the browser can retry verify.
   Also a nightly job re-reads every open subscription from Razorpay and fixes any row that
   disagrees.

**Renewing and ending**

8. ✅ A renewal fails: `pending` while Razorpay retries (Premium only until `current_end`), then
   `halted` and locked.
9. ➕ The mandate is revoked in the UPI app: the next charge fails (case 8), and a banner says
   "Your autopay was stopped; renew to keep Premium".
10. ➕ Cancels, then changes their mind before the period ends: "Resume" if Razorpay allows it,
    otherwise a new subscription.
11. ✅ Switches plans: later (answer 5).
12. ✅ Clocks disagree: Razorpay's `current_end` is the only end time used.

**Security and trust**

13. ✅★ Fake or replayed webhook: a bad signature is refused, and each event id is stored once.
14. ✅ The page is edited to look premium: the server checks on every premium request.
15. ➕★ `/verify` is called with someone else's subscription: it must carry the caller's
    `student_id` in its notes (set when we created it), or it is refused.
16. ➕ A secret leaks: a written "rotate the keys" step (new keys in Razorpay, `wrangler secret
    put`, redeploy).

**Accounts**

17. ➕★ Deletes their Aventra account while subscribed: the subscription is cancelled on Razorpay
    first (immediately, not at period end), then the account is deleted. Otherwise they keep being
    charged for an account that's gone.
18. ✅ Signs up again with another email: a new free account; the Billing page says Premium belongs
    to the account that paid.
19. ➕ Has two accounts (Google one day, LinkedIn the next): Premium stays on one; "Contact us" to
    move it, by hand in `/admin`.

**Money and support**

20. ➕★ Refund or chargeback: a `refund` or `dispute` webhook ends Premium at once, and the Refunds
    page states the policy (answer 4).
21. ✅ A price changes: existing subscribers keep their plan; a new price is a new plan.
22. ✅ The free fit-check count: "3 a day" means the last 24 hours, like the other limits.

**Product**

23. ✅ Premium lapses with saved chats and connections: readable, not continuable (answer 3).
24. ✅ You and beta testers: `premium_grants` with an end date, set in `/admin`.
25. ✅ The code ships before Razorpay approves the account: nothing is locked until `PREMIUM=on`.
