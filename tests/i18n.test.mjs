// Every translation key a page uses must exist, in all five locales.
//   node --test tests/i18n.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import vm from 'node:vm';

const root = new URL('../public/', import.meta.url);
const read = (p) => readFileSync(new URL(p, root), 'utf8');

const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(read('js/i18n/translations.js'), sandbox);
const { CARE_LOCALES: locales, CARE_TRANSLATIONS: tables } = sandbox.window;

const flatten = (obj, prefix = '') =>
  Object.entries(obj).flatMap(([k, v]) => (typeof v === 'object' ? flatten(v, `${prefix}${k}.`) : [`${prefix}${k}`]));

const files = [
  ...readdirSync(root).filter((f) => f.endsWith('.html')),
  ...readdirSync(new URL('js/', root)).filter((f) => f.endsWith('.js')).map((f) => `js/${f}`),
  ...readdirSync(new URL('js/pages/', root)).map((f) => `js/pages/${f}`),
];

export function usedKeys() {
  const used = new Map();
  const patterns = [
    /data-i18n(?:-placeholder|-aria|-html)?="([a-zA-Z0-9_.]+)"/g,
    /data-page-title-i18n="([a-zA-Z0-9_.]+)"/g,
    /(?:careT|\bt|CareI18n\.t)\(\s*'([a-zA-Z]+\.[a-zA-Z0-9_.]+?)'\s*[,)]/g,
  ];
  for (const file of files) {
    const text = read(file);
    for (const pattern of patterns)
      for (const m of text.matchAll(pattern)) if (!used.has(m[1])) used.set(m[1], file);
  }
  return used;
}

test('all locales have exactly the same keys', () => {
  const en = flatten(tables.en).sort();
  for (const locale of locales) assert.deepEqual(flatten(tables[locale]).sort(), en, locale);
});

test('every key used by a page exists', () => {
  const known = new Set(flatten(tables.en));
  const missing = [...usedKeys()].filter(([key]) => !known.has(key)).map(([key, file]) => `${key} (${file})`);
  assert.deepEqual(missing, []);
});

test('no translation is empty', () => {
  for (const locale of locales)
    for (const key of flatten(tables[locale])) {
      const value = key.split('.').reduce((o, k) => o[k], tables[locale]);
      assert.ok(String(value).trim(), `${locale}.${key}`);
    }
});
