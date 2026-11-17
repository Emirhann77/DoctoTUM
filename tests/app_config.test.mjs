// Runtime config: API base and email-link origin for web, local dev and the native app.
//   node --test tests/app_config.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { resolveCareConfig, PROD_API_BASE, PROD_WEB_ORIGIN } = require('../public/js/config.js');

test('native app uses hosted API and web origin even though hostname is localhost', () => {
  assert.deepEqual(
    resolveCareConfig({ protocol: 'capacitor:', hostname: 'localhost', origin: 'capacitor://localhost' }, {}),
    { apiBase: PROD_API_BASE, webOrigin: PROD_WEB_ORIGIN, isNativeApp: true }
  );
});

test('local dev uses localhost:8000 and its own origin', () => {
  for (const [hostname, origin] of [['localhost', 'http://localhost:3000'], ['127.0.0.1', 'http://127.0.0.1:8080']]) {
    assert.deepEqual(resolveCareConfig({ protocol: 'http:', hostname, origin }, {}),
      { apiBase: 'http://localhost:8000', webOrigin: origin, isNativeApp: false });
  }
});

test('hosted web uses hosted API and its own origin', () => {
  assert.deepEqual(
    resolveCareConfig({ protocol: 'https:', hostname: 'careconnect-web.onrender.com', origin: PROD_WEB_ORIGIN }, {}),
    { apiBase: PROD_API_BASE, webOrigin: PROD_WEB_ORIGIN, isNativeApp: false }
  );
});

test('explicit overrides win', () => {
  const c = resolveCareConfig({ protocol: 'capacitor:', hostname: 'localhost', origin: 'capacitor://localhost' },
    { apiBase: 'https://x.test', webOrigin: 'https://y.test' });
  assert.equal(c.apiBase, 'https://x.test');
  assert.equal(c.webOrigin, 'https://y.test');
});

test('every page loads config.js before auth.js and api.js', () => {
  const dir = new URL('../public/', import.meta.url);
  const pages = readdirSync(dir).filter((f) => f.endsWith('.html'));
  assert.ok(pages.length >= 11);
  for (const f of pages) {
    const html = readFileSync(new URL(f, dir), 'utf8');
    const cfg = html.indexOf('js/config.js');
    assert.ok(cfg !== -1, `${f} missing js/config.js`);
    const auth = html.indexOf('js/auth.js');
    if (auth !== -1) assert.ok(cfg < auth, `${f}: config.js must precede auth.js`);
    const api = html.indexOf('js/api.js');
    if (api !== -1) assert.ok(cfg < api, `${f}: config.js must precede api.js`);
  }
});

test('every page serves supabase-js and tailwind from public/vendor, never from a CDN', () => {
  const dir = new URL('../public/', import.meta.url);
  const pages = readdirSync(dir).filter((f) => f.endsWith('.html'));
  assert.ok(pages.length >= 11);
  const plain = new Set(['login.html', 'signup.html', 'verify.html', 'reset-password.html']);
  const failures = [];
  for (const page of pages) {
    const html = readFileSync(new URL(page, dir), 'utf8');
    const srcs = [...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"/g)].map((m) => m[1]);
    const remote = srcs.filter((s) => /^https?:/i.test(s));
    if (remote.length) failures.push(`${page}: remote script ${remote.join(', ')}`);
    const sb = srcs.indexOf('vendor/supabase-js.umd.js');
    const cfg = srcs.indexOf('js/config.js');
    if (sb === -1 || cfg === -1 || sb > cfg) failures.push(`${page}: vendor/supabase-js.umd.js must load before js/config.js`);
    const tw = srcs.filter((s) => s === 'vendor/tailwind-play.js' || s === 'vendor/tailwind-play-forms-cq.js');
    const want = plain.has(page) ? 'vendor/tailwind-play.js' : 'vendor/tailwind-play-forms-cq.js';
    if (tw.length !== 1 || tw[0] !== want) failures.push(`${page}: expected exactly ${want}, got ${tw.join(', ') || 'none'}`);
  }
  assert.deepEqual(failures, []);
});

test('capacitor shell is configured for the iOS app', () => {
  const cfg = JSON.parse(readFileSync(new URL('../capacitor.config.json', import.meta.url), 'utf8'));
  assert.equal(cfg.appId, 'io.doctotum.careconnect');
  assert.equal(cfg.appName, 'CareConnect');
  assert.equal(cfg.webDir, 'public');
  assert.equal(cfg.ios.contentInset, 'always');
});

test('iOS Info.plist declares no non-exempt encryption and the display name', () => {
  const plist = readFileSync(new URL('../ios/App/App/Info.plist', import.meta.url), 'utf8');
  assert.match(plist, /<key>ITSAppUsesNonExemptEncryption<\/key>\s*<false\/>/);
  assert.match(plist, /<key>CFBundleDisplayName<\/key>\s*<string>CareConnect<\/string>/);
});

test('codemagic workflow guards the App Store app id placeholder', () => {
  const yml = readFileSync(new URL('../codemagic.yaml', import.meta.url), 'utf8');
  assert.match(yml, /ios-testflight:/);
  assert.match(yml, /bundle_identifier: io\.doctotum\.careconnect/);
  assert.match(yml, /0000000000/);
  assert.match(yml, /xcode-project build-ipa --project ios\/App\/App\.xcodeproj --scheme App/);
});
