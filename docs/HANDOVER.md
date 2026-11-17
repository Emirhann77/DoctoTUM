# Handover: end-to-end build (night of 17–18 November 2026)

Branch `feat/end-to-end`, not pushed. Plan: `docs/superpowers/plans/2026-11-18-end-to-end.md`.

## Try it

```bash
npm run dev            # http://localhost:3000/index.html
npm run backend:dev    # http://localhost:8000  (activate .venv first)
```

Sign in with the test account: the email and password are in `.env.local` as `E2E_TEST_EMAIL` and `E2E_TEST_PASSWORD`. It has three sample prescriptions, a filled-in profile, two pharmacy requests and the Pro plan.

## What works, against the real Supabase project

Checked in a browser at phone size, signed in as the test account, in English and German:

| Flow | Result |
|---|---|
| Login, wrong password, sign-out, protected pages redirect to login | works |
| Home: own name, next appointment, medications, open orders, notifications | works |
| Symptom check → matched doctors from the database → booking with the reason carried over | works |
| "Save to my health record" on the symptom check | works |
| My appointments: list, double-booking refused, cancel | works |
| Pharmacy: own prescriptions, refill and medication requests, order list, cancel | works |
| Profile: details, conditions, allergies saved and read back; age and conditions pre-fill the symptom check | works |
| SOS: hold → alert saved → "Call 112" button; contacts add/remove; Medical ID from the profile | works |
| SOS while signed out: button, call screen and phone numbers still work | works |
| Plans: choice saved, shown on profile and home | works (no payment) |

Automated: 199 backend tests, 34 browser-logic tests, and 13 opt-in tests that run against the live project (`RUN_LIVE=1 python -m pytest backend/tests/test_live.py`), including that a second user cannot read or change the first user's data.

## Reviews run overnight and what they changed

- **Security** (ECC): database rules let an owner rewrite their own role, plan, bookings and orders through the database API. Closed in `20261118100000_harden_rls.sql`; demo mode made opt-in; unknown signing-key ids can no longer force a key refetch per request.
- **Backend correctness** (ECC): database errors were surfacing as the wrong status (an expired token as "not found", a missing row as a server error). Mapped properly; the doctor list keeps serving the last good copy during an outage.
- **Clinical safety** (ECC):
  - an expired login could navigate away from the Call 112 screen; SOS calls no longer sign anyone out
  - the SOS page was behind login; it now works signed out
  - "I can’t breathe" typed with a phone's curly apostrophe was not recognised as an emergency; fixed in both the backend and the browser
  - "overdose", "unconscious", "not breathing", "seizure" and "want to die" added to the emergency phrases
  - emergency messages now carry a direct Call 112 button instead of sending people to another page
  - a result that points at mental health shows 112 and 116 123
  - "drink plenty of water" is withheld when a long-term condition is on record; self-care tips and over-the-counter items carry a caveat
  - removing an allergy asks for confirmation
- **Standards and plan conformance** (Matt Pocock code review): per-card error states on home, demo doctors labelled when the directory is unreachable, plan buttons translated, unused API wrappers removed.

Left as they are, by choice: some duplicated helpers across page scripts (loading/empty/error blocks, initials), `'/mo'` and unit suffixes not translated, and the orders page does not check a request against the allergies in the profile.

## What is simulated or missing

- **Payments.** Choosing a plan and sending a pharmacy request take no money. Stripe was not touched, as asked.
- **Emergency dispatch.** The app never contacts emergency services. It records the alert and shows a button that dials 112.
- **Video calls.** The fake call screen was removed. There is no video.
- **Doctors' side.** There is no doctor login or screen. Doctors and the sample prescriptions are seeded rows. Requests and bookings are stored; nobody receives them.
- **Vitals, health score, lab results.** Still illustrative numbers, now labelled "Sample data".
- **AI assistant.** Not verified live: the OpenAI key in `.env.local` returned "no credits remaining" on the first call. The app falls back to built-in replies and now says so in the chat. Add credits and it switches over with no code change.
- **Sign-up by email.** Not exercised: it sends a real confirmation email, and Supabase's built-in mailer allows only a few per hour. The form is unchanged from before; the database trigger that creates the profile on sign-up is verified (it ran for the test account).
- **The expired-login case on SOS** is fixed in code and covered by reading, not reproduced in a browser (it needs a token to expire mid-session).
- **Deployment.** Nothing has been deployed or built yet; the hosted setup is defined in `render.yaml` and `codemagic.yaml` (see "iOS app (TestFlight pilot)"). Locally the pages use `http://localhost:8000`.

## Decisions made without you

1. **New Supabase project wired in.** `public/js/auth.js` now points at the project in `.env.local`. All six migrations were applied to it with `psql`.
2. **Database rules tightened** (`20261118100000_harden_rls.sql`) after a security review found that a signed-in person could, by calling the database directly, set their own role or tier, give themselves a plan, rewrite a booking's doctor or status, or order against someone else's prescription. Those are closed and covered by live tests.
3. **The backend no longer trusts a user id from the browser.** It verifies the Supabase token (this project signs with ES256) and acts as that user, so the database rules still apply.
4. **Keyless demo mode is opt-in.** With no Supabase settings the API used to serve everyone as one demo user. It now refuses unless `CARECONNECT_ALLOW_DEMO_USER=1`.
5. **Patients cannot add prescriptions.** The old "Add prescription" form let anyone invent one. It is now "Request a medication", which creates a pharmacy request.
6. **The chat is labelled as an AI assistant.** It used to appear under each doctor's name and photo.
7. **SOS wording and numbers changed.** "CALLING EMERGENCY — Help is on the way" was shown while nothing was called. The numbers were US ones (911, 988); they are now 112, 116 117 and 116 123.
8. **Demo person removed.** "Alex Johnson", his insurance card, contacts and nearby hospitals are gone; pages show the signed-in person's data or an empty state.
9. **Legacy English text.** New text is translated into all five languages. Older hard-coded English on the plans page and a few labels on home was left as it was.

## For you to decide

- **"HIPAA Compliant" and "Board Certified" on the plans page** are claims this prototype cannot back up. I left your copy alone; I recommend removing them before anyone outside sees the page.
- **The triage rules and medical wording are a developer's draft**, not clinically reviewed (`public/data/care_rules.json`).
- **Language-first matching.** A doctor who speaks the patient's language can outrank the exact specialist.
- **Rotate the database password** if this machine is shared: `DATABASE_URL` in `.env.local` contains it. Nothing secret was committed (checked).
- **`/` still shows the Supabase status page**; the product is at `/index.html`.

## iOS app (TestFlight pilot)

This is a TestFlight pilot only, on an individual Apple developer account. An App Store release needs an organization account (Apple expects health apps to come from an organization, guideline 5.1.1(ix)), a privacy policy, and no simulated billing or pharmacy features.

### What is set up (in the repo, not yet run)

- `public/js/config.js` picks the API base and the email-link origin. In the app (`capacitor:`) and on the hosted web the API is `https://careconnect-api.onrender.com`; email links use `https://careconnect-web.onrender.com`. Locally it is `http://localhost:8000`. Every page loads it right before `js/auth.js`.
- `public/vendor/` holds supabase-js and Tailwind Play; no page loads scripts from a CDN. Tailwind compiles in the browser and logs a "not for production" warning.
- `render.yaml`: Blueprint for the API and the static site (`public/`). `plan: starter` on the API is a paid Render plan, chosen so the API doesn't sleep; the free plan sleeps after 15 minutes idle and takes about a minute to wake.
- Capacitor shell in `ios/` (appId `io.doctotum.careconnect`). After changing `public/`, run `npx cap sync ios`.
- `codemagic.yaml`: manual workflow `ios-testflight`, build number = latest TestFlight build + 1, uploads to TestFlight. `APP_STORE_APP_ID` is the placeholder `0000000000`, so the build fails until you replace it.
- The app icon and splash screen are Capacitor's defaults; replace them before inviting external testers (for example with `@capacitor/assets`). `xcode: latest` in `codemagic.yaml` should be pinned once the first build is green.
- Tests: `tests/app_config.test.mjs`, `backend/tests/test_cors.py`.

Nothing here has been deployed, built in CI or installed on a device.

### Your one-time setup

1. Render: create the Blueprint from `render.yaml` and enter the five secrets in the dashboard, each with the same name as in `.env.local`, except the anon key:
   - `SUPABASE_URL` = `SUPABASE_URL`
   - `SUPABASE_ANON_KEY` = the value of `NEXT_PUBLIC_SUPABASE_ANON_KEY` (the public anon key that is also in `public/js/auth.js`)
   - `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENAI_API_KEY` = same names
   Do not set `CARECONNECT_ALLOW_DEMO_USER`.
   Then verify: `curl https://careconnect-api.onrender.com/api/integrations/status` must show `"data_store": "supabase"` and `"auth": "supabase_token"` (also `"specialists_source": "supabase"`). `"data_store": "in_memory"` or `"auth": "demo_user"` means a secret is missing or wrong; fix it before going on.
2. Supabase Auth: add the hosted `verify.html` and `reset-password.html` URLs (on `careconnect-web.onrender.com`) to the redirect URLs.
3. Apple Developer: individual account. Register the bundle ID `io.doctotum.careconnect` in the Apple Developer portal (Certificates, Identifiers & Profiles -> Identifiers).
4. App Store Connect: create the app record for that bundle ID, and an API key (Team key, App Manager role).
5. Codemagic: add the API key as integration `careconnect_asc`. In Codemagic's code signing identities settings, generate or upload an Apple Distribution certificate and fetch an App Store provisioning profile for `io.doctotum.careconnect` (Codemagic can create both using the API key integration).
6. Replace `APP_STORE_APP_ID` in `codemagic.yaml` with the app's Apple ID; start `ios-testflight` manually.

### Device check (pending first TestFlight build)

Add yourself as an internal tester (no Beta App Review), install, then record pass or fail:

- [ ] Test account signs in
- [ ] Kill the app and reopen: still signed in
- [ ] Headers are clear of the notch
- [ ] Doctor list is the real list (bookable), not the fallback
- [ ] Book an appointment, then cancel it
- [ ] SOS: the alert is recorded, and `tel:112` opens the call sheet
- [ ] Symptom check: an emergency phrase shows the 112 path, and the `tel:` links work
- [ ] Pharmacy and plans show their simulated labels
- [ ] Language switch works
- [ ] Sign up with a new email: the link opens `careconnect-web.onrender.com/verify.html`
- [ ] Password reset: the link opens the web reset page, and signing in to the app with the new password works
- [ ] Airplane mode: pages show their error states and don't hang

Rule: if a `tel:` link does not open the call sheet, file it as its own fix task and invite no testers until it is fixed. Do not ship a build where the SOS call button does nothing.

## Where things are

```
public/                 pages; js/api.js (backend calls), js/records.js (own rows via Supabase), js/pages/*.js
public/js/config.js     API base and email-link origin (web, local dev, native app)
public/vendor/          supabase-js and Tailwind Play, served locally
ios/                    Capacitor iOS shell
capacitor.config.json   Capacitor config (appId io.doctotum.careconnect)
render.yaml             Render Blueprint (API + static site)
codemagic.yaml          iOS TestFlight workflow
backend/auth.py         token verification
backend/store/          per-user data access: memory.py (tests), supabase.py (real)
backend/routes/         one file per area
backend/scripts/seed_demo.py   recreates the test account
supabase/migrations/    schema; the last two files are from this session
tests/, backend/tests/  npm test, npm run backend:test
```
