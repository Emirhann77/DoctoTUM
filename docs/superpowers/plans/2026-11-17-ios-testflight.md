# iOS TestFlight Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the existing CareConnect static app to iPhone testers through TestFlight, talking to a hosted backend.

**Architecture:** Capacitor wraps `public/` unchanged as the iOS app's web content. A small runtime config (`public/js/config.js`) decides the API base and the origin used in email links, depending on whether the page runs locally, on the hosted web or inside the app. FastAPI and a static copy of `public/` (for the email verify/reset pages) are deployed to Render from a `render.yaml` blueprint. Codemagic builds, signs and uploads the iOS app from GitHub, because there is no Mac.

**Tech Stack:** Capacitor (iOS, Swift Package Manager), Render (Python web service + static site), Codemagic (macOS M2, App Store Connect API key), existing FastAPI / Supabase / static JS.

**Spec:** The decisions made in this conversation on 2026-11-17: TestFlight pilot (not a public App Store release), no Mac so builds run in the cloud on Codemagic, backend on Render, personal Apple Developer account.

## Global Constraints

- Bundle ID: `io.doctotum.careconnect`. **Confirm during review.** It can't be changed after the App Store Connect record exists.
- App display name: `CareConnect`.
- Render service names: `careconnect-api` (backend) and `careconnect-web` (static site), region `frankfurt`. If Render assigns different URLs, Task 3 Step 6 updates the two constants in `config.js`.
- No secret goes into `public/`, `render.yaml` or `codemagic.yaml`. The service-role key, JWT secret and OpenAI key are entered only in the Render dashboard. The App Store Connect key goes only into Codemagic.
- `CARECONNECT_ALLOW_DEMO_USER` must never be set on Render.
- The existing rules in CLAUDE.md still apply: no health data in localStorage or URLs; the SOS page never implies that help was sent; simulated features say so on screen.
- Every new or changed page script is covered by `npm test`, and `npm test` and `npm run backend:test` both stay green.

## Review Focus

1. **The SOS and symptom-check `tel:112` / `tel:116123` links inside the app**: tapping one must open the iOS call sheet, never do nothing. This is checked on a device in Task 5.
2. **Inside the app, `location` is `capacitor://localhost`**: the app must use the hosted API, not `http://localhost:8000`. Pinned by the `capacitor:` test case in Task 1.
3. **Signup and password reset started in the app**: the email link must point at `https://careconnect-web.onrender.com/...`, not `capacitor://localhost/...`. Pinned in Task 1 (`webOrigin`) and checked by hand in Task 5.
4. **The backend is asleep or unreachable when the app opens**: pages must show their existing error or empty states instead of hanging. The free Render plan sleeps after 15 minutes and takes about a minute to wake, so `render.yaml` uses `plan: starter`. Checked on a device in Task 5.
5. **iOS kills the app and the user reopens it**: they should still be signed in (Supabase session in WKWebView storage), and headers shouldn't sit under the notch or status bar (`contentInset: "always"`). Checked on a device in Task 5.

---

### Task 1: Runtime config for API base and email-link origin

**Files:**
- Create: `public/js/config.js`
- Modify: `public/js/api.js:6`, `public/js/auth.js:60,84`, all 11 `public/*.html` (load `js/config.js` immediately before `js/auth.js`)
- Test: `tests/app_config.test.mjs`; add it to the `test` script in `package.json`

**Interfaces:**
- Produces: `resolveCareConfig(loc: {protocol, hostname, origin}, overrides: {apiBase?, webOrigin?}) -> {apiBase: string, webOrigin: string, isNativeApp: boolean}`; global `window.CARE_CONFIG` set from `location` plus `window.CARE_API_BASE` / `window.CARE_WEB_ORIGIN`; constants `PROD_API_BASE = 'https://careconnect-api.onrender.com'`, `PROD_WEB_ORIGIN = 'https://careconnect-web.onrender.com'`. Use the same UMD pattern as the end of `public/js/navigator.js` (`module.exports` when present).

- [ ] **Step 1: Write the failing tests** in `tests/app_config.test.mjs` (load with `createRequire`, like `navigator.test.mjs`):

```js
const { resolveCareConfig, PROD_API_BASE, PROD_WEB_ORIGIN } = require('../public/js/config.js');
test('native app uses hosted API and web origin even though hostname is localhost', () => {
  assert.deepEqual(resolveCareConfig({ protocol: 'capacitor:', hostname: 'localhost', origin: 'capacitor://localhost' }, {}),
    { apiBase: PROD_API_BASE, webOrigin: PROD_WEB_ORIGIN, isNativeApp: true });
});
test('local dev uses localhost:8000 and its own origin', () => {
  for (const [hostname, origin] of [['localhost', 'http://localhost:3000'], ['127.0.0.1', 'http://127.0.0.1:8080']])
    assert.deepEqual(resolveCareConfig({ protocol: 'http:', hostname, origin }, {}),
      { apiBase: 'http://localhost:8000', webOrigin: origin, isNativeApp: false });
});
test('hosted web uses hosted API and its own origin', () => {
  assert.deepEqual(resolveCareConfig({ protocol: 'https:', hostname: 'careconnect-web.onrender.com', origin: PROD_WEB_ORIGIN }, {}),
    { apiBase: PROD_API_BASE, webOrigin: PROD_WEB_ORIGIN, isNativeApp: false });
});
test('explicit overrides win', () => {
  const c = resolveCareConfig({ protocol: 'capacitor:', hostname: 'localhost', origin: 'capacitor://localhost' },
    { apiBase: 'https://x.test', webOrigin: 'https://y.test' });
  assert.equal(c.apiBase, 'https://x.test'); assert.equal(c.webOrigin, 'https://y.test');
});
test('every page loads config.js before auth.js and api.js', () => {
  // for each public/*.html: indexOf('js/config.js') !== -1 and < indexOf('js/auth.js'); and < indexOf('js/api.js') when api.js is present
});
```

- [ ] **Step 2: Run `npm test` and confirm it fails.** Expected: `Cannot find module '../public/js/config.js'`.
- [ ] **Step 3: Implement `config.js`.** In `api.js`, change `API_BASE` to `(window.CARE_CONFIG && window.CARE_CONFIG.apiBase) || window.CARE_API_BASE || 'http://localhost:8000'`. Keep the `typeof window` guard, because `navigator.test.mjs` loads `api.js` in a sandbox without `CARE_CONFIG`. In `auth.js`, build both redirect URLs from `CARE_CONFIG.webOrigin` instead of `location.origin`. Add the `<script src="js/config.js"></script>` tag to the 11 pages.
- [ ] **Step 4: Run `npm test`.** Expected: all pass, including the existing navigator and i18n tests.
- [ ] **Step 5: Commit** with `feat(app): runtime config for API base and email-link origin`.

### Task 2: Serve CDN scripts from the app itself

The app shouldn't depend on unpinned CDN scripts at startup (`supabase-js@2` currently floats to whatever the latest 2.x is). Google Fonts stay remote, and the app falls back to system fonts if they don't load.

**Files:**
- Create: `public/vendor/supabase-js.umd.js` (exact pinned 2.x version; write the version in a first-line comment), `public/vendor/tailwind-play.js` (from `https://cdn.tailwindcss.com/3.4.17`), `public/vendor/tailwind-play-forms-cq.js` (from `https://cdn.tailwindcss.com/3.4.17?plugins=forms,container-queries`)
- Modify: all 11 `public/*.html` script tags. Pages that currently load the plugin build get `tailwind-play-forms-cq.js`. `login`, `signup`, `verify` and `reset-password` get `tailwind-play.js`, so their inputs don't pick up `@tailwindcss/forms` styling.
- Test: add to `tests/app_config.test.mjs`

- [ ] **Step 1: Write the failing test.** For every `public/*.html`: no `<script` tag has a `src` starting with `http`; the page loads `vendor/supabase-js.umd.js` before `js/config.js`; it loads exactly one of the two tailwind vendor files, and pages that had `?plugins=` get the forms-cq file.
- [ ] **Step 2: Run `npm test`.** Expected: FAIL, listing the 11 pages.
- [ ] **Step 3: Download the three files with `curl -L`, then change the script tags.** Check each download is JavaScript, not an HTML error page. For example, `head -c 200` should not start with `<`.
- [ ] **Step 4: Run `npm test`.** Expected: PASS. Then run `npm run dev` and open `/login.html`, `/index.html` and `/sos.html`. The styling should look the same as before and the console should have no errors.
- [ ] **Step 5: Commit** with `chore(app): vendor supabase-js and tailwind instead of loading from CDNs`.

### Task 3: Deploy backend and web copy to Render

**Files:**
- Create: `render.yaml`, `backend/tests/test_cors.py`
- Modify: `public/js/config.js` (only if Render assigns different URLs)

**Interfaces:**
- Consumes: `backend.main.create_app()`, which reads `CORS_ALLOW_ORIGINS` when called.
- Produces: `https://careconnect-api.onrender.com` (`/api/*`) and `https://careconnect-web.onrender.com` (the `public/` pages).

- [ ] **Step 1: Write the test** in `backend/tests/test_cors.py`. Use `monkeypatch.setenv("CORS_ALLOW_ORIGINS", "capacitor://localhost,https://careconnect-web.onrender.com")`, then call `create_app()`, then send an `OPTIONS /api/specialists` preflight with `Access-Control-Request-Method: GET`. Assert that `access-control-allow-origin` echoes `capacitor://localhost` and `https://careconnect-web.onrender.com`, and is absent for `https://evil.example`.
- [ ] **Step 2: Run `npm run backend:test`.** Expected: PASS straight away, because `main.py:52` already supports the variable. The test pins that behaviour for the app, so no code change is needed.
- [ ] **Step 3: Write `render.yaml`.**
  - Web service `careconnect-api`: `runtime: python`, `plan: starter`, `region: frankfurt`, `buildCommand: pip install -r backend/requirements.txt`, `startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, `healthCheckPath: /api/integrations/status`.
  - Its env vars: `PYTHON_VERSION=3.12.8`, `CORS_ALLOW_ORIGINS=capacitor://localhost,https://careconnect-web.onrender.com`, `OPENAI_MODEL=gpt-4o-mini`, and these with `sync: false` (values entered in the dashboard): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENAI_API_KEY`.
  - Static site `careconnect-web`: `staticPublishPath: public`, `buildCommand: echo static`, and the same three security headers as `vercel.json`.
- [ ] **Step 4: Ask the user before pushing.** Push `feat/end-to-end` to `origin`, then the user creates the services in the Render dashboard: New → Blueprint → this repo and branch → enter the secret values from `.env.local`.
- [ ] **Step 5: Verify.** `curl https://careconnect-api.onrender.com/api/integrations/status` should report the Supabase store, Supabase auth and OpenAI, and not demo mode. Opening `https://careconnect-web.onrender.com/login.html` should let the test account sign in, and the home page should load real data.
- [ ] **Step 6: If Render gave different URLs**, update `PROD_API_BASE`, `PROD_WEB_ORIGIN` and `CORS_ALLOW_ORIGINS`, then run `npm test`.
- [ ] **Step 7: Supabase dashboard (user).** Under Auth → URL Configuration, add `https://careconnect-web.onrender.com/verify.html` and `https://careconnect-web.onrender.com/reset-password.html` to Redirect URLs.
- [ ] **Step 8: Commit** with `feat(deploy): render blueprint for API and web; pin CORS for the iOS app`.

### Task 4: Capacitor iOS shell and Codemagic TestFlight workflow

**Files:**
- Create: `capacitor.config.json`, `ios/` (generated), `codemagic.yaml`
- Modify: `package.json` (add `@capacitor/core` and `@capacitor/ios` to dependencies and `@capacitor/cli` to devDependencies, with exact versions from the latest stable major), `ios/App/App/Info.plist`
- Test: add to `tests/app_config.test.mjs`

- [ ] **Step 1: Write the failing test.** `capacitor.config.json` has `appId === 'io.doctotum.careconnect'`, `appName === 'CareConnect'`, `webDir === 'public'` and `ios.contentInset === 'always'`. `ios/App/App/Info.plist` contains `<key>ITSAppUsesNonExemptEncryption</key>` followed by `<false/>`.
- [ ] **Step 2: Run `npm test`.** Expected: FAIL, because the file is missing.
- [ ] **Step 3: Set up Capacitor.** Install the packages, write `capacitor.config.json`, run `npx cap add ios` (choose the SPM package manager if the CLI asks), then edit `Info.plist` (add the encryption key and set `CFBundleDisplayName` to `CareConnect`). Run `npx cap sync ios`. Expected: no errors. Warnings about Xcode or CocoaPods missing on Windows are fine. Check that `ios/.gitignore` ignores `App/App/public`.
- [ ] **Step 4: Run `npm test`.** Expected: PASS. Also run `npm run build`. Expected: the Next build is unaffected.
- [ ] **Step 5: Write `codemagic.yaml`** with one workflow, `ios-testflight`:
  - Triggering: manual only.
  - `instance_type: mac_mini_m2`, `environment: { xcode: latest, node: 22, ios_signing: { distribution_type: app_store, bundle_identifier: io.doctotum.careconnect }, vars: { APP_STORE_APP_ID: <from App Store Connect> } }`, and `integrations: { app_store_connect: careconnect_asc }`.
  - Scripts: `npm ci`; `npx cap sync ios`; `xcode-project use-profiles`; `cd ios/App && agvtool new-version -all $(($(app-store-connect get-latest-testflight-build-number "$APP_STORE_APP_ID") + 1))`; `xcode-project build-ipa --project ios/App/App.xcodeproj --scheme App`.
  - Artifacts: `build/ios/ipa/*.ipa`.
  - `publishing.app_store_connect: { auth: integration, submit_to_testflight: true }`.
- [ ] **Step 6: Apple and Codemagic setup (user).**
  1. Enrol in the Apple Developer Program as an individual.
  2. In App Store Connect, register the bundle ID and create the app record. If the name "CareConnect" is taken, pick another; that only changes the store name. Copy the Apple ID number into `APP_STORE_APP_ID`.
  3. Under Users and Access → Integrations, create a Team API key with the App Manager role.
  4. In Codemagic: sign up with GitHub, add the repo, and add the API key under Team integrations → Developer Portal with the name `careconnect_asc`.
- [ ] **Step 7: Commit, ask the user, push, then start `ios-testflight` in Codemagic.** Commit message: `feat(ios): capacitor shell and codemagic testflight workflow`. Expected: the build is green and, after processing (usually 5–30 minutes), it appears in App Store Connect → TestFlight.

### Task 5: On-device verification and docs

**Files:**
- Modify: `docs/HANDOVER.md` (new "iOS app" section), `CLAUDE.md` (Deployment section: Render, Capacitor, Codemagic, `config.js`, vendored scripts, the rule that pages load `js/config.js` before `js/auth.js`)

- [ ] **Step 1: Install on an iPhone.** Add yourself as an internal tester in TestFlight; internal testers need no Beta App Review. Install the build.
- [ ] **Step 2: Go through the checklist and record pass or fail for each item in HANDOVER.**
  - Test account signs in.
  - Kill the app and reopen it: still signed in.
  - Headers are clear of the notch.
  - The doctor list is the real list (bookable), not the fallback.
  - Book an appointment, then cancel it.
  - SOS: the alert is recorded, and **`tel:112` opens the call sheet**.
  - Symptom check: an emergency phrase shows the 112 path, and the `tel:` links work.
  - Pharmacy and plans show their simulated labels.
  - Language switch works.
  - Sign up with a new email: the link opens `careconnect-web.onrender.com/verify.html`.
  - Password reset: the link opens the web reset page, and signing in to the app with the new password works.
  - Airplane mode: pages show their error states and don't hang.
- [ ] **Step 3: If `tel:` links don't open the call sheet**, file the failure as its own fix task before testers are invited. Don't ship a build where the SOS call button does nothing.
- [ ] **Step 4: Update the docs.** In HANDOVER and CLAUDE.md, state that this is a TestFlight pilot only, and that an App Store release needs an organization account, a privacy policy and no simulated billing or pharmacy features.
- [ ] **Step 5: Commit** with `docs: iOS TestFlight pilot setup and device check results`.
