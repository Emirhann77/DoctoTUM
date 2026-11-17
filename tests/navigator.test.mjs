// Runs the shared triage cases against the browser implementation.
//   node --test tests/navigator.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const root = new URL('..', import.meta.url);
const read = (p) => readFileSync(new URL(p, root), 'utf8');
const require = createRequire(import.meta.url);

const { evaluate, rank } = require('../public/js/navigator.js');
const rules = JSON.parse(read('public/data/care_rules.json'));
const cases = JSON.parse(read('tests/care_rules.cases.json'));

// js/api.js and js/doctors.js are plain browser scripts; load them into a sandbox.
const sandbox = { window: {}, console };
vm.createContext(sandbox);
vm.runInContext(
  read('public/js/api.js') + '\n' + read('public/js/doctors.js') +
    '\nthis.checkEmergencySymptoms = checkEmergencySymptoms; this.EMERGENCY_PHRASES = EMERGENCY_PHRASES;' +
    '\nthis.FALLBACK_DOCTORS = FALLBACK_DOCTORS;',
  sandbox,
);
const { checkEmergencySymptoms, EMERGENCY_PHRASES, FALLBACK_DOCTORS } = sandbox;

for (const c of cases) {
  test(c.name, () => {
    const out = evaluate(rules, c.input, checkEmergencySymptoms);
    assert.equal(out.urgency, c.urgency);
    assert.equal(out.specialty_slug, c.specialty);
    for (const tip of c.tips_exclude || []) assert.ok(!out.self_care.includes(tip), tip);
  });
}

test('every emergency phrase escalates, including in capitals', () => {
  for (const phrase of EMERGENCY_PHRASES) {
    for (const text of [phrase, phrase.toUpperCase(), phrase.toLocaleUpperCase('tr')]) {
      const out = evaluate(
        rules,
        { symptoms: ['cough'], severity: 1, duration: 'today', age: 30, description: 'x ' + text + ' y' },
        checkEmergencySymptoms,
      );
      assert.equal(out.urgency, 'emergency', text);
    }
  }
});

test('language match outranks an otherwise equal doctor', () => {
  const ranked = rank(FALLBACK_DOCTORS, 'dermatology', 'es', 'Munich', 3);
  assert.equal(ranked[0].doctor.name, 'Dr. Marcus Williams');
  assert.deepEqual([...ranked[0].reasons], ['specialty', 'language', 'available', 'nearby']);
});

test('doctors outside the specialty are not offered, GPs stand in', () => {
  const ranked = rank(FALLBACK_DOCTORS, 'mental_health', 'en', '', 10);
  assert.deepEqual(ranked.map((m) => m.doctor.specialtySlug).sort(), ['general', 'mental_health']);
});
