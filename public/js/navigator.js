// Care Navigator — browser side.
//
// CareNavigator.navigate() asks the backend (POST /api/care/navigate) and, when it is
// unreachable, runs the same rules locally so the page keeps working (the repo-wide
// "API down -> still usable" convention).
//
// evaluate() and rank() mirror backend/services/care_navigator.py. Both read
// public/data/care_rules.json, and both are run against tests/care_rules.cases.json
// (npm test, npm run backend:test). Change them together.
(function (global) {
  var URGENCY_RISK = { emergency: 'high', urgent: 'medium', routine: 'low', self_care: 'low' };

  function result(urgency, specialty, reasons, redFlags, tips) {
    return {
      urgency: urgency,
      risk_level: URGENCY_RISK[urgency],
      specialty_slug: specialty,
      reasons: reasons,
      red_flags: redFlags,
      self_care: tips,
    };
  }

  function unique(list) {
    return list.filter(function (x, i) { return x && list.indexOf(x) === i; });
  }

  // emergencyCheck: (text) => { isEmergency, matched } — checkEmergencySymptoms from js/api.js
  function evaluate(rules, input, emergencyCheck) {
    var catalog = rules.symptoms;
    var th = rules.thresholds;
    var slugs = unique(input.symptoms || []);
    var known = slugs.filter(function (s) { return Object.prototype.hasOwnProperty.call(catalog, s); });
    var hasUnknown = known.length !== slugs.length;
    var conditions = (input.known_conditions || []).filter(function (c) { return c && String(c).trim(); });
    var severity = input.severity, age = input.age, duration = input.duration;

    var redFlags = known.filter(function (s) { return catalog[s].red_flag; });
    var phraseHit = emergencyCheck(input.description || '').isEmergency;
    if (redFlags.length || phraseHit) {
      var why = [];
      if (redFlags.length) why.push('red_flag_symptom');
      if (phraseHit) why.push('emergency_phrase');
      return result('emergency', 'emergency', why, redFlags, []);
    }

    var has = function (s) { return known.indexOf(s) !== -1; };
    var longLasting = duration === 'days_4_7' || duration === 'over_week';
    var higherRisk = age < th.infant_age || age >= th.senior_age || conditions.length > 0;

    var urgent = [];
    if (severity >= th.urgent_severity) urgent.push('high_severity');
    if (age < th.infant_age && has('fever')) urgent.push('infant_fever');
    if (has('fever') && longLasting) urgent.push('prolonged_fever');
    if (age >= th.senior_age && severity >= th.elevated_risk_severity) urgent.push('senior_moderate');
    if (conditions.length && severity >= th.elevated_risk_severity) urgent.push('conditions_moderate');

    var routine = [];
    if (severity >= th.moderate_severity) routine.push('moderate_severity');
    if (longLasting) routine.push('persistent');
    if (!known.length || hasUnknown || known.some(function (s) { return !catalog[s].self_care_ok; }))
      routine.push('needs_assessment');
    if (higherRisk) routine.push('higher_risk_group');

    var urgency, reasons;
    if (urgent.length) { urgency = 'urgent'; reasons = urgent; }
    else if (routine.length) { urgency = 'routine'; reasons = routine; }
    else { urgency = 'self_care'; reasons = ['mild_short']; }

    var tips = [];
    known.forEach(function (s) {
      (catalog[s].tips || []).forEach(function (t) { if (tips.indexOf(t) === -1) tips.push(t); });
    });

    return result(urgency, pickSpecialty(known, catalog, age, th), reasons, [], tips.slice(0, 4));
  }

  function pickSpecialty(known, catalog, age, th) {
    if (age < th.child_age) return 'pediatrics';
    var votes = {};
    known.forEach(function (s) { votes[catalog[s].specialty] = (votes[catalog[s].specialty] || 0) + 1; });
    var names = Object.keys(votes);
    if (!names.length) return 'general';
    var top = Math.max.apply(null, names.map(function (n) { return votes[n]; }));
    var winners = names.filter(function (n) { return votes[n] === top; });
    return winners.length === 1 ? winners[0] : 'general';
  }

  // doctors: records from normalizeDoctorRecord (js/doctors.js)
  function rank(doctors, specialty, language, city, limit) {
    var lang = String(language || '').trim().toLowerCase();
    var cityL = String(city || '').trim().toLowerCase();
    var ranked = [];
    doctors.forEach(function (doc) {
      if (doc.specialtySlug === 'emergency') return; // reached through SOS, not booking
      var score = 0, reasons = [];
      if (doc.specialtySlug === specialty) { score += 40; reasons.push('specialty'); }
      else if (doc.specialtySlug === 'general') score += 15;
      else return;
      if (lang && (doc.languageCodes || []).indexOf(lang) !== -1) { score += 30; reasons.push('language'); }
      if (doc.available) { score += 20; reasons.push('available'); }
      if (cityL && cityL === String(doc.city || '').trim().toLowerCase()) { score += 10; reasons.push('nearby'); }
      ranked.push({ doctor: doc, score: score, reasons: reasons });
    });
    ranked.sort(function (a, b) { return b.score - a.score || a.doctor.name.localeCompare(b.doctor.name); });
    return ranked.slice(0, limit || 3);
  }

  var rulesPromise = null;
  function loadRules() {
    if (!rulesPromise) {
      rulesPromise = fetch('data/care_rules.json')
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .catch(function (err) {
          console.warn('[navigator] rules unavailable', err.message);
          rulesPromise = null;
          return null;
        });
    }
    return rulesPromise;
  }

  // With neither backend nor rules we can still screen for emergencies; everything
  // else goes to a clinician. Never self-care from a position of ignorance.
  function evaluateWithoutRules(input, emergencyCheck) {
    if (emergencyCheck(input.description || '').isEmergency)
      return result('emergency', 'emergency', ['emergency_phrase'], [], []);
    return result('routine', 'general', ['needs_assessment'], [], []);
  }

  // input: { symptoms, description, severity, duration, age, known_conditions }
  // prefs: { language, preferred_consult_language, location: { city, country } }
  async function navigate(input, prefs) {
    prefs = prefs || {};
    var matchLanguage = prefs.preferred_consult_language || prefs.language || '';

    var remote = typeof careNavigate === 'function' ? await careNavigate(input) : null;
    if (remote && remote.urgency) {
      return {
        urgency: remote.urgency,
        risk_level: remote.risk_level,
        specialty_slug: remote.specialty_slug,
        reasons: remote.reasons || [],
        red_flags: remote.red_flags || [],
        self_care: remote.self_care || [],
        match_language: remote.match_language || matchLanguage,
        matches: (remote.matches || []).map(function (m) {
          return { doctor: doctorFromApi(m.specialist), score: m.score, reasons: m.reasons || [] };
        }),
        source: 'api',
      };
    }

    var rules = await loadRules();
    var local = rules
      ? evaluate(rules, input, checkEmergencySymptoms)
      : evaluateWithoutRules(input, checkEmergencySymptoms);
    local.match_language = matchLanguage;
    local.matches =
      local.urgency === 'emergency'
        ? []
        : rank(FALLBACK_DOCTORS, local.specialty_slug, matchLanguage, (prefs.location || {}).city, 3);
    local.source = 'local';
    return local;
  }

  var api = { evaluate: evaluate, rank: rank, loadRules: loadRules, navigate: navigate };
  global.CareNavigator = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
