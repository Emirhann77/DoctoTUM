# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DoctoTUM (branded "CareConnect" in the UI and in many identifiers) is a telehealth prototype. The repo holds three pieces:

1. **Static HTML app** (`public/`: `index.html`, `check.html`, `consult.html`, `pharmacy.html`, `profile.html`, `sos.html`, `plans.html`, plus `login/signup/verify/reset-password.html`) — this is the real product UI.
2. **FastAPI backend** (`backend/`) — verifies Supabase tokens and reads/writes Supabase as the signed-in user; in-memory store for tests; optional OpenAI.
3. **Next.js 15 app** (`app/`, `lib/`, `middleware.ts`) — serves `public/` as static files, plus a Supabase connectivity status page at `/` and the `/auth/callback` code-exchange route. The product home is `/index.html` (or `/home` via `vercel.json`), not `/`.

## Commands

```bash
npm run dev            # Next.js on :3000 — the product UI is at /index.html
npm run build
npm run lint           # next lint (next/core-web-vitals)

pip install -r backend/requirements.txt   # or backend/requirements-dev.txt to run tests
npm run backend:dev    # uvicorn backend.main:app --reload --port 8000  (run from repo root; imports are `backend.*`)
npx cap sync ios       # copy public/ into the iOS project (after any change to public/)
```

- The static pages are served by `npm run dev`, or by any static file server rooted at `public/` (e.g. `python -m http.server 8080 --directory public`). Backend CORS allows localhost/127.0.0.1 on ports 3000, 5173, 5500, 8080; add others via `CORS_ALLOW_ORIGINS` (comma-separated).
- Tests: `npm test` (Node: `tests/navigator.test.mjs`, `tests/i18n.test.mjs`, `tests/app_config.test.mjs` for config resolution, script order, no remote scripts and the Capacitor/Codemagic config) and `npm run backend:test` (pytest, `backend/tests/`). Both run the shared cases in `tests/care_rules.cases.json`. No Python linter config.
- FastAPI docs: `http://localhost:8000/docs`. `GET /api/integrations/status` reports the data store, auth mode and AI mode.
- Env: copy `.env.example` to `.env.local`. The backend loads `.env` then `.env.local` (override) from the cwd, so both Next and FastAPI share that file.

## Architecture

### Who owns what

- **Browser → Supabase directly** (`public/js/records.js`) for simple rows one person owns: profile, medical details, conditions, allergies, emergency contacts, saved symptom checks. Row-level security is the protection.
- **Browser → FastAPI** (`public/js/api.js`) for anything with rules across tables: doctors, appointments, prescriptions (read-only), pharmacy orders, SOS log, plans, AI chat, symptom check.
- **FastAPI → Supabase as the user**: the backend verifies the access token, then calls PostgREST with the anon key plus that token, so row-level security still applies. The service-role key is used only for the doctor directory and for subscriptions.
- Identity comes only from the verified token. No route accepts a user id from the client.

### Static frontend (`public/`; no bundler, everything is a global)

Paths in this section are relative to `public/`. Each page: Tailwind Play from `vendor/` (compiles in the browser; logs a "not for production" warning, expected) with an **inline `tailwind.config` copied into every page's `<head>`**, Supabase JS v2 from `vendor/`, then plain `<script>` tags. No page loads scripts from a CDN (Google Fonts is still remote). **Script order matters**:

1. `vendor/supabase-js.umd.js` → `js/config.js` → `js/auth.js` (in `<head>`; `config.js` must come immediately before `auth.js`): `config.js` sets `window.CARE_CONFIG` (`apiBase`, `webOrigin`, `isNativeApp`); `auth.js` has `getSupabase`, `getSession`, `getUser`, `requireAuth`, `signIn`, `signOut`, `getAccessToken`, … Holds the project URL and anon key (public by design).
2. `js/i18n/translations.js` → `js/i18n/i18n.js` (`CarePrefs`, `CareI18n`, auto-bootstrap) → `js/i18n/languageContext.js`
3. `js/ui.js`: `escapeHtml`, `careT(key, vars, fallback)`, `showToast`, `stateBlockHTML`, `apiErrorText`, date formatting
4. `js/api.js`: `apiCall(path)` → `{ ok, status, data, error }` (status 0 = backend unreachable; 401 signs the user out), `apiFetch` (data or null), endpoint wrappers
5. as needed: `js/records.js` (`CareRecords`), `js/doctors.js`, `js/navigator.js` (`CareNavigator`)
6. the page script: `js/pages/<page>.js` for home, pharmacy, profile, sos, plans; `consult.html` and `check.html` still carry theirs inline. Each starts with `await requireAuth()`.

Conventions:

- **No demo person.** A page shows the signed-in person's data, an empty state, or an error state (`stateBlockHTML`). Only the doctor list and the symptom-check rules fall back to built-in data when the backend is down; the fallback doctors cannot be booked.
- **Anything simulated says so on screen** (plans, pharmacy requests, sample vitals). The SOS page must never imply that help has been sent: the app records the alert and shows a `tel:112` button.
- **Escape everything** that goes into `innerHTML` or an attribute (`escapeHtml`; `consult.html` also has `escapeAttr`/`escapeJsQuoted` for its inline handlers). Doctor ids are UUID strings.
- **i18n.** `data-i18n`, `data-i18n-placeholder`, `data-i18n-aria`, `<body data-page-title-i18n>`; dotted keys with `{{var}}`. Locales `en, de, tr, es, fr`. JS-rendered text uses `careT()` and re-renders on `careconnect:redraw-dynamic`. `tests/i18n.test.mjs` fails if a used key is missing or the locales differ; add keys to all five. Some legacy text on plans/home is still hard-coded English.
- **Preferences** (language, location, consult language) are in localStorage under `careconnect_*`. Health details never go in localStorage or URLs; the symptom-check → consult hand-off uses `sessionStorage` (`careconnect_check_handoff`) and is removed on read.
- Design tokens are duplicated inline in every page; a theme change must be applied to each.
- `lib/i18n/` (repo root) is an unused React-side stub.

### Auth

Supabase Auth only. `backend/auth.py` `current_user` verifies the bearer token: ES256/RS256 against the project's JWKS (cached 10 min, refetch on unknown key at most once a minute, stale keys kept if the fetch fails) or HS256 against `SUPABASE_JWT_SECRET`; audience `authenticated`, issuer checked. It never decodes unverified. With nothing configured the API answers 503 unless `CARECONNECT_ALLOW_DEMO_USER=1` (then a fixed demo user on the in-memory store). The Next.js side (`lib/supabase/*`, `middleware.ts`) is the standard `@supabase/ssr` setup and is independent of the static pages' session.

### Backend (`backend/`)

`main.py` mounts routers under `/api`; `routes/` (thin) → `store/` or `services/` → `models/schemas.py`.

- `store/base.py`: the `Store` protocol (one instance per signed-in user) and `NotFound`/`Conflict`/`Unavailable`, mapped to 404/409/503 by a handler in `main.py`. `store/memory.py` is used by tests and demo mode; `store/supabase.py` is PostgREST as the user. **Keep the two behaving the same**: the route tests run on memory, `tests/test_supabase_store.py` fakes PostgREST, `tests/test_live.py` (opt-in, `RUN_LIVE=1`) hits the real project.
- Appointments are `consultations` rows with `scheduled_at`; API status `booked` = database `queued`. Cancelling sets `cancelled`. A unique index stops two live bookings at the same time (409).
- `services/directory.py`: doctors from `providers` (service role, cached 60 s, serves the last good list during an outage) or the in-memory list. Never mixed.
- `services/billing.py`: plans. **Simulated**: records the choice with the service role, never charges.
- `services/care_navigator.py`, `POST /api/care/navigate`: deterministic symptom check. Rules are data in `public/data/care_rules.json`, also read by `public/js/navigator.js` (offline fallback mirroring `evaluate`/`rank_specialists`). Change both evaluators together and add a case to `tests/care_rules.cases.json`. Unknown input routes to a clinician, never to self-care. The API returns reason/tip codes; the page localizes them.
- `services/ai_responses.py`: OpenAI over `httpx` when `OPENAI_API_KEY` is set, otherwise built-in replies; failures are logged and the response carries `source: "openai" | "rules"`. AI routes are rate-limited per user (`utils/rate_limit.py`).
- `utils/safety.py`: emergency-phrase screening runs before any model call. The list (en/de/tr/es/fr, Turkish-aware case folding) is mirrored in `public/js/api.js`; a pytest fails if they differ.
- `scripts/seed_demo.py`: creates the confirmed test account and sample prescriptions; writes its credentials to `.env.local`.
- Tests set `CARECONNECT_SKIP_DOTENV` so `.env.local` never leaks into them.

### Database (`supabase/migrations/`)

Plain SQL, applied in filename order with `psql "$DATABASE_URL" -f …` (or the SQL editor). RLS on every table, keyed to `auth.uid()`; `handle_new_user` creates the `profiles` row on signup. `20261118100000_harden_rls.sql` restricts what an owner can change through the database API: profile role/tier, subscriptions (read-only), consultations (book and cancel only), orders (request and cancel only), alerts (no delete). `anon` has no table access. When adding a table, add owner policies and think about which columns the owner may write, not just which rows.

### Deployment

`public/js/config.js` decides the API base and the origin used in email links: on `localhost` the API is `http://localhost:8000`; on the hosted web and inside the iOS app (`capacitor:`) it is `https://careconnect-api.onrender.com`, and in the app email links (signup verify, password reset) use `https://careconnect-web.onrender.com`. `window.CARE_API_BASE` / `window.CARE_WEB_ORIGIN` override.

- `vercel.json` adds clean URLs for the pages in `public/` and security headers.
- `render.yaml` defines the Render Blueprint: API `careconnect-api` (secrets are `sync: false`, entered in the Render dashboard; CORS allows `capacitor://localhost` and the web origin) and static site `careconnect-web` (publishes `public/`). Never set `CARECONNECT_ALLOW_DEMO_USER` there. Whether it is deployed is not recorded in the repo.
- iOS: Capacitor shell in `ios/` (`capacitor.config.json`, webDir `public`). After changing `public/`, run `npx cap sync ios`. There is no Mac: `codemagic.yaml` (manual workflow `ios-testflight`) builds and uploads to TestFlight; one-time setup is in its header comment. This is a **TestFlight pilot only**: an App Store release needs an organization account, a privacy policy and no simulated billing or pharmacy features.

See `docs/HANDOVER.md` for what is real, what is simulated and what was not verified.
