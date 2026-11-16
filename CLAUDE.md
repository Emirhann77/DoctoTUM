# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DoctoTUM (branded "CareConnect" in the UI and in many identifiers) is a telehealth prototype. The repo holds three pieces:

1. **Static HTML app** (`public/`: `index.html`, `check.html`, `consult.html`, `pharmacy.html`, `profile.html`, `sos.html`, `plans.html`, plus `login/signup/verify/reset-password.html`) — this is the real product UI.
2. **FastAPI backend** (`backend/`) — mock/in-memory API plus optional OpenAI and Supabase integrations.
3. **Next.js 15 app** (`app/`, `lib/`, `middleware.ts`) — serves `public/` as static files, plus a Supabase connectivity status page at `/` and the `/auth/callback` code-exchange route. The product home is `/index.html` (or `/home` via `vercel.json`), not `/`.

## Commands

```bash
npm run dev            # Next.js on :3000 — the product UI is at /index.html
npm run build
npm run lint           # next lint (next/core-web-vitals)

pip install -r backend/requirements.txt   # or backend/requirements-dev.txt to run tests
npm run backend:dev    # uvicorn backend.main:app --reload --port 8000  (run from repo root; imports are `backend.*`)
```

- The static pages are served by `npm run dev`, or by any static file server rooted at `public/` (e.g. `python -m http.server 8080 --directory public`). Backend CORS allows localhost/127.0.0.1 on ports 3000, 5173, 5500, 8080; add others via `CORS_ALLOW_ORIGINS` (comma-separated).
- Tests: `npm test` (Node, `tests/navigator.test.mjs`, browser-side triage in `public/js/navigator.js`) and `npm run backend:test` (pytest, `backend/tests/`). Both run the shared cases in `tests/care_rules.cases.json`. No Python linter config.
- FastAPI docs: `http://localhost:8000/docs`. `GET /api/integrations/status` reports whether AI and specialists are running in mock or live mode.
- Env: copy `.env.example` to `.env.local`. The backend loads `.env` then `.env.local` (override) from the cwd, so both Next and FastAPI share that file.

## Architecture

### Static frontend (`public/`; no bundler, everything is a global)

Paths in this section are relative to `public/`.

Each page is self-contained: Tailwind via CDN with an **inline `tailwind.config` copied into every page's `<head>`**, Supabase JS v2 via CDN, then plain `<script>` tags. Nothing is a module; files communicate through globals, so **script order matters**:

1. Supabase CDN → `js/auth.js` (in `<head>`) — defines `getSupabase`, `getSession`, `getUser`, `requireAuth`, `signIn`, `signUp`, `signOut`, `getAccessToken`, …
2. `js/i18n/translations.js` → `window.CARE_LOCALES`, `window.CARE_TRANSLATIONS`
3. `js/i18n/i18n.js` → `window.CarePrefs` (localStorage prefs) and `window.CareI18n`; auto-runs `CareI18n.bootstrap()` on `DOMContentLoaded`
4. `js/i18n/languageContext.js` → `window.LanguageContext` façade
5. `js/api.js` → `apiFetch` and endpoint wrappers; feature-detects `getUser`/`getAccessToken`/`CarePrefs` with `typeof` checks
   - `consult.html` and `check.html` then load `js/doctors.js` (doctor record helpers, `FALLBACK_DOCTORS`); `check.html` also loads `js/navigator.js` (`window.CareNavigator`)
6. The page's own inline script, which starts with `await requireAuth()` (redirects to `login.html` when there is no session)

Things that span files:

- **Design tokens are duplicated.** The Material-style color/spacing/font theme lives inline in every HTML page — a theme change must be applied to each page.
- **i18n.** Static text uses `data-i18n`, `data-i18n-html`, `data-i18n-placeholder`, `data-i18n-aria`, and `<body data-page-title-i18n>`; keys are dotted paths (`consult.title`) into `CARE_TRANSLATIONS[locale]`, with `{{var}}` interpolation. Locales: `en, de, tr, es, fr` — a new key must be added to all five. JS-rendered content must call `CareI18n.t()` and re-render on the `careconnect:redraw-dynamic` window event (fired on bootstrap and language change). Other events: `careconnect:locale`, `careconnect:location`, `careconnect:consultlang`.
- **Preferences** (language, location, preferred consult language) live in localStorage under `careconnect_*` keys and are attached to AI-chat and emergency payloads by `js/api.js`.
- **API failures are swallowed.** `apiFetch` returns `null` on any error and logs a warning; every page is expected to fall back to hard-coded demo data, so the UI works with the backend down. Base URL defaults to `http://localhost:8000`; override with `window.CARE_API_BASE` set before `js/api.js` loads.
- **Inline `onclick` handlers** are built from template strings in several pages; values interpolated into attributes must go through the page's `escapeAttr`/escape helpers (recent fixes were for exactly this).
- `lib/i18n/` (repo root) is a React-side stub (`languageContext.tsx` reads the same `careconnect_language` key); it is not used by any page yet.

### Auth

Supabase Auth is the only auth system. `public/js/auth.js` creates the browser client (with the project URL and anon key hard-coded as fallbacks to `window.SUPABASE_URL` / `window.SUPABASE_ANON`), and email links redirect to `verify.html` / `reset-password.html`. The Next.js side (`lib/supabase/{client,server,middleware}.ts`, `middleware.ts`) is the standard `@supabase/ssr` cookie-refresh setup and is independent of the static pages' localStorage session.

`public/js/api.js` sends the Supabase access token as `Authorization: Bearer …`, and `backend/utils/auth_verify.py` provides `require_auth` / `optional_auth` dependencies — but **no route uses them yet**. Routes still take a numeric `user_id` from the client; `getCurrentUserId()` hashes the Supabase UUID to an int for the mock store. Also note `verify_supabase_token` decodes tokens *without verifying the signature* when `SUPABASE_JWT_SECRET` is unset.

### Backend (`backend/`)

`main.py` mounts all routers under `/api`. Layering: `routes/` (thin) → `services/` + `database/db.py` → `models/schemas.py` (Pydantic).

- `database/db.py` is an **in-memory mock store** (module-level dicts/lists); appointments and prescriptions vanish on restart, and with `--reload` on every code change.
- `services/supabase_sync.py`: specialists come from the Supabase `providers` table via REST when `SUPABASE_URL` (or `NEXT_PUBLIC_SUPABASE_URL`) and `SUPABASE_SERVICE_ROLE_KEY` are set, otherwise from the mock list. Provider UUIDs are mapped to ints with `zlib.crc32` (stable across processes); `POST /api/appointments` validates `specialist_id` against the same unified list.
- `services/ai_responses.py`: chat and triage call OpenAI over raw `httpx` when `OPENAI_API_KEY` is set (`OPENAI_MODEL`, default `gpt-4o-mini`), otherwise return deterministic keyword-based mock replies. Any OpenAI error silently falls back to the mock.
- **Care Navigator** (`services/care_navigator.py`, `POST /api/care/navigate`, UI in `check.html`): deterministic symptom check → urgency (`emergency | urgent | routine | self_care`) + specialty + specialists ranked by specialty, spoken language, availability, city. Rules are data in `public/data/care_rules.json`, read by both the backend and `public/js/navigator.js` (the offline fallback, which mirrors `evaluate`/`rank_specialists`). Change the two evaluators together; add a case to `tests/care_rules.cases.json` for any rule change. Unknown input must route to a clinician, never to self-care. The API returns reason/tip *codes*; the page localizes them (`check.reasons.*`, `check.tips.*`). `check.html` hands a booking to `consult.html` through `sessionStorage` (`careconnect_check_handoff`), and writes to Supabase `user_symptoms` only when the user taps save.
- `utils/safety.py`: emergency-phrase screening runs **before** any model call and short-circuits to a high-risk "seek emergency care" response. The phrase list (en/de/tr/es/fr, matched after Turkish-aware case folding) is mirrored in `public/js/api.js` (`EMERGENCY_PHRASES`, `foldForMatch`) — a pytest fails if the two lists differ.

### Database (`supabase/migrations/`)

Plain SQL migrations for the real schema (profiles, medical profiles, providers, consultations, prescriptions, pharmacy orders, subscriptions/plans, family groups, emergency alerts, symptoms), with RLS policies on every table keyed to `auth.uid()` and a `handle_new_user` trigger that creates a `profiles` row on signup. Applied via the Supabase SQL editor or `supabase db push`. Apart from `providers`, the FastAPI backend does not read or write these tables yet — its Pydantic models (int user ids) do not match the SQL schema (UUIDs).

### Deployment

`vercel.json` adds clean URLs for the pages in `public/` (`cleanUrls`, `/home` → `/index.html`, etc.) and security headers. The backend is not deployed by this config.
