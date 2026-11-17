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
- **Deployment.** Nothing was deployed. `http://localhost:8000` is still the API address the pages use by default.

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

## Where things are

```
public/                 pages; js/api.js (backend calls), js/records.js (own rows via Supabase), js/pages/*.js
backend/auth.py         token verification
backend/store/          per-user data access: memory.py (tests), supabase.py (real)
backend/routes/         one file per area
backend/scripts/seed_demo.py   recreates the test account
supabase/migrations/    schema; the last two files are from this session
tests/, backend/tests/  npm test, npm run backend:test
```
