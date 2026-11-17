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
