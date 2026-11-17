# DoctoTUM

A telehealth prototype (branded **CareConnect** in the UI): check your symptoms, get matched with a doctor who speaks your language, book a visit, manage prescriptions, and reach emergency help.

## Layout

```
public/      The product UI: static HTML pages, plain JS (js/), triage rules (data/)
backend/     FastAPI API (routes/ -> services/ -> database/, models/), tests, requirements
supabase/    SQL migrations for the real schema (RLS on every table)
app/, lib/   Next.js app: serves public/ (routes in next.config.ts), plus /auth/callback
tests/       Browser-logic tests and the triage cases shared with the backend tests
```

Config files at the root (`package.json`, `next.config.ts`, `tsconfig.json`, `middleware.ts`, `vercel.json`, `.eslintrc.json`) are where their tools expect them.

## Run it

```bash
npm install
cp .env.example .env.local                  # fill in Supabase values
npm run dev                                 # http://localhost:3000/index.html

python -m venv .venv                        # then activate it
pip install -r backend/requirements-dev.txt
npm run backend:dev                         # http://localhost:8000/docs
```

Apply the SQL files in `supabase/migrations/` (in filename order) to your Supabase project, then create a test account with `python -m backend.scripts.seed_demo`.

Payments, video calls and emergency dispatch are not connected; see `docs/HANDOVER.md` for what is real and what is simulated.

## Test

```bash
npm test                # browser-side triage logic and translation completeness (Node)
npm run backend:test    # API, auth, triage rules, emergency screening (pytest)
RUN_LIVE=1 python -m pytest backend/tests/test_live.py   # against the real Supabase project
npm run lint
```

See `CLAUDE.md` for architecture notes.
