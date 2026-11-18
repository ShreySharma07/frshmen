# Turning on sign-in (Part B.1)

The code is in place: `/login`, `/profile`, and `db/postgres/0004_profiles.sql`, which the
Supabase migrations workflow applies when it reaches `main`. These settings live outside the
repo, so Shrey sets them once. Until steps 1-4 are done, `/login` and `/profile` say sign-in
isn't switched on yet.

`<ref>` below is the Supabase project's reference: the part before `.supabase.co` in its URL.

## 1. Supabase: where sign-in may return to
Supabase dashboard → **Authentication → URL Configuration**
- Site URL: `https://aventra.getaventra.workers.dev`
- Redirect URLs: add `https://aventra.getaventra.workers.dev/profile` and, for local work,
  `http://localhost:3000/profile`

Any other address is refused, so a sign-in link can't be bounced to someone else's site.

## 2. Google sign-in
In [Google Cloud Console](https://console.cloud.google.com/):
1. **APIs & Services → OAuth consent screen**: External, app name Aventra, your support email.
   Scopes: only the defaults (email, profile, openid). Gmail scopes come later, in B.5.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID** → Web application.
   - Authorized JavaScript origins: `https://aventra.getaventra.workers.dev`
   - Authorized redirect URIs: `https://<ref>.supabase.co/auth/v1/callback`
3. Copy the client ID and client secret into Supabase → **Authentication → Sign In / Providers →
   Google** and turn it on. The secret stays in Supabase; never put it in the repo.

While the consent screen is in "Testing", only the test users you list can sign in with Google.
Publishing it is free.

## 3. Email links
Supabase → **Authentication → Sign In / Providers → Email** is on by default. Supabase's own
mailer sends about 2 emails an hour, which is enough for testing. For launch, see step 6.

## 4. GitHub: the site's public settings
GitHub repo → **Settings → Secrets and variables → Actions → Variables** (not Secrets):
- `SUPABASE_URL` = `https://<ref>.supabase.co`
- `SUPABASE_PUBLISHABLE_KEY` = the `sb_publishable_...` key from Supabase → **Project Settings →
  API Keys**

Both are public by design: the browser needs them, and they reach only what RLS allows. Never
use the secret (`sb_secret_...`) or service-role key here. Then re-run the **Deploy site**
workflow.

## 5. Check it
1. Open `/login` and sign in with Google, then with an email link.
2. On `/profile`, fill everything in, upload a PDF, and save.
3. In Supabase → **Table Editor → students**, there is one row with your id; in **Storage →
   resumes** there is `<your id>/resume.pdf`.

## 6. Before launch: Resend for email (decided 2026-10-30)
1. Buy the domain (the project's one paid item, about $10 a year).
2. In Resend, add the domain and the DNS records it asks for.
3. Supabase → **Authentication → Emails → SMTP Settings**: host `smtp.resend.com`, port `465`,
   username `resend`, password = a Resend API key, sender like `signin@<domain>`.
   Resend's free tier allows 3,000 emails a month and 100 a day.

## 7. Before launch: a check on email sign-in links (decided 2026-11-18, security review M1)
Without it, a script can ask for thousands of sign-in links, one per throwaway inbox, and each new
inbox is a new account. Google and LinkedIn sign-ins aren't affected: they verify the email
themselves. Email links already prove the inbox belongs to the person (they must click the link),
so "email confirmation" is already in place for every way in.

Do these **in this order**. Turning CAPTCHA on in Supabase before the site sends tokens would
break email sign-in until the next deploy.

1. Cloudflare dashboard → **Turnstile** → **Add widget**. Name `Aventra sign-in`, hostnames
   `aventra.getaventra.workers.dev` (later also your own domain) and `localhost`. Widget mode
   **Managed**. Copy the **site key** and the **secret key**.
2. GitHub → **Settings → Secrets and variables → Actions → Variables**:
   `TURNSTILE_SITE_KEY` = the site key (public by design). Re-run **Deploy site**, then open
   `/login` and check that the email button works.
3. Supabase → **Authentication → Attack Protection** → turn on **Enable CAPTCHA protection**,
   provider **Turnstile**, and paste the **secret key**. The secret stays in Supabase; never put it
   in the repo.
4. Check: sign out, then send yourself a link from `/login`. It should arrive as before. A request
   without a token (e.g. a script) now gets "captcha verification process failed".

While you're on Attack Protection: also check **Authentication → Sign In / Providers → Email** has
"Confirm email" on (the default), and **Authentication → Rate Limits** keeps "Emails sent" low.
