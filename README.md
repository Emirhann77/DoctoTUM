# DoctoTUM

A telehealth prototype (branded **CareConnect** in the UI): check your symptoms, get matched with a doctor who speaks your language, book a visit, manage prescriptions, and reach emergency help.

## Layout

```
public/      The product UI: static HTML pages, plain JS (js/), triage rules (data/)
backend/     FastAPI API (routes/ -> services/ -> database/, models/), tests, requirements
supabase/    SQL migrations for the real schema (RLS on every table)
app/, lib/   Next.js app: serves public/, plus a Supabase status page and /auth/callback
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

The UI works without the backend: every page falls back to demo data.

## Test

```bash
npm test                # browser-side triage logic (Node)
npm run backend:test    # API, triage rules, emergency screening (pytest)
npm run lint
```

See `CLAUDE.md` for architecture notes.
