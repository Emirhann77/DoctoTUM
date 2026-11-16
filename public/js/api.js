// CareConnect API client — talks to the FastAPI backend (backend/main.py)
// Set window.CARE_API_BASE before loading this script to override the default.
const API_BASE = (typeof window !== 'undefined' && window.CARE_API_BASE) || 'http://localhost:8000';

// Returns the numeric user id from the active Supabase session, falling back to demo
async function getCurrentUserId() {
  if (typeof getUser === 'function') {
    const user = await getUser();
    if (user) {
      // Supabase user.id is a UUID — hash to a stable int for the mock db
      return Math.abs(user.id.split('-').join('').slice(0, 8).split('').reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 0)) || 1;
    }
  }
  return 1; // demo fallback
}

async function apiFetch(path, options = {}) {
  try {
    // Attach JWT if auth.js is loaded and a session exists
    let authHeader = {};
    if (typeof getAccessToken === 'function') {
      const token = await getAccessToken();
      if (token) authHeader = { Authorization: `Bearer ${token}` };
    }

    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...authHeader, ...options.headers },
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[api] ${path} failed — using fallback data.`, err.message);
    return null;
  }
}

// ---------- Specialists ----------

async function getSpecialists() {
  return apiFetch('/api/specialists');
}

async function getAvailableSpecialists() {
  return apiFetch('/api/specialists/available');
}

// ---------- Appointments ----------

async function getAppointments() {
  const userId = await getCurrentUserId();
  return apiFetch(`/api/appointments?user_id=${userId}`);
}

async function bookAppointment({ specialistId, startTime, reason = '' }) {
  const userId = await getCurrentUserId();
  return apiFetch('/api/appointments', {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId,
      specialist_id: specialistId,
      start_time: startTime,
      reason,
    }),
  });
}

async function cancelAppointment(appointmentId) {
  return apiFetch(`/api/appointments/${appointmentId}`, { method: 'DELETE' });
}

// ---------- AI Assistant ----------

function preferenceContextPayload() {
  if (typeof window === 'undefined' || typeof CarePrefs === 'undefined') return {};
  var loc = CarePrefs.getLocationForPayload && CarePrefs.getLocationForPayload();
  var prefConsult =
    typeof CarePrefs.getPreferredConsultLanguage === 'function'
      ? CarePrefs.getPreferredConsultLanguage()
      : '';
  return {
    language: CarePrefs.getLanguage(),
    ...(loc ? { location: loc } : {}),
    ...(prefConsult ? { preferred_consult_language: prefConsult } : {}),
  };
}

async function aiChat(message) {
  const userId = await getCurrentUserId();
  return apiFetch('/api/ai_assistant/chat', {
    method: 'POST',
    body: JSON.stringify({
      user_message: message,
      user_id: userId,
      ...preferenceContextPayload(),
    }),
  });
}

async function triageSymptoms({ symptoms, age = 30, knownConditions = [], duration = 'unknown' }) {
  return apiFetch('/api/ai_assistant/triage', {
    method: 'POST',
    body: JSON.stringify({
      symptoms,
      age,
      known_conditions: knownConditions,
      duration,
    }),
  });
}

// ---------- Care Navigator ----------

// input: { symptoms: [slug], description, severity, duration, age, known_conditions }
async function careNavigate(input) {
  return apiFetch('/api/care/navigate', {
    method: 'POST',
    body: JSON.stringify({ ...input, ...preferenceContextPayload() }),
  });
}

// Writes the check to the signed-in user's own rows in Supabase `user_symptoms`
// (RLS: user_id = auth.uid()). Only called when the user explicitly asks to save.
// labels: { slug: English label } used when a slug is not in symptom_definitions.
async function saveSymptomCheck({ symptoms, description, severity, labels = {} }) {
  try {
    const client = typeof getSupabase === 'function' ? getSupabase() : null;
    const user = typeof getUser === 'function' ? await getUser() : null;
    if (!client || !user) return false;

    let idBySlug = {};
    if (symptoms.length) {
      const { data, error } = await client.from('symptom_definitions').select('id, slug').in('slug', symptoms);
      if (error) throw error;
      (data || []).forEach((row) => { idBySlug[row.slug] = row.id; });
    }
    const base = { user_id: user.id, severity, notes: description || null };
    const rows = symptoms.length
      ? symptoms.map((slug) =>
          idBySlug[slug] ? { ...base, symptom_id: idBySlug[slug] } : { ...base, custom_label: labels[slug] || slug })
      : [{ ...base, custom_label: (description || '').slice(0, 80) }];
    const { error } = await client.from('user_symptoms').insert(rows);
    if (error) throw error;
    return true;
  } catch (err) {
    console.warn('[api] saving symptom check failed', err.message || err);
    return false;
  }
}

// ---------- Emergency ----------

async function startEmergency(symptomsOrPayload = '') {
  const userId = await getCurrentUserId();
  const body =
    typeof symptomsOrPayload === 'object' &&
    symptomsOrPayload !== null &&
    !Array.isArray(symptomsOrPayload)
      ? { user_id: userId, ...symptomsOrPayload }
      : { user_id: userId, symptoms: symptomsOrPayload || '' };

  body.preferred_language =
    typeof CarePrefs !== 'undefined'
      ? CarePrefs.getLanguage()
      : body.preferred_language;

  var locPref =
    typeof CarePrefs !== 'undefined' &&
    typeof CarePrefs.getLocationForPayload === 'function'
      ? CarePrefs.getLocationForPayload()
      : null;
  if (locPref && !body.location) body.location = locPref;

  return apiFetch('/api/emergency/start', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

async function endEmergency(sessionId) {
  return apiFetch('/api/emergency/end', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  });
}

// ---------- Prescriptions ----------

async function getPrescriptions() {
  const userId = await getCurrentUserId();
  return apiFetch(`/api/prescriptions?user_id=${userId}`);
}

async function createPrescription({ medication, dosage, instructions, prescribedBy }) {
  const userId = await getCurrentUserId();
  return apiFetch('/api/prescriptions', {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId,
      medication,
      dosage,
      instructions,
      prescribed_by: prescribedBy,
    }),
  });
}

// ---------- Risk level helpers (mirrors backend/utils/safety.py) ----------

const EMERGENCY_PHRASES = [
  "chest pain",
  "pressure in my chest",
  "difficulty breathing",
  "can't breathe",
  "cant breathe",
  "shortness of breath",
  "loss of consciousness",
  "passed out",
  "fainted",
  "stroke",
  "face drooping",
  "arm weakness",
  "slurred speech",
  "severe bleeding",
  "bleeding heavily",
  "suicidal",
  "suicidal thoughts",
  "kill myself",
  "self harm",
  "severe allergic reaction",
  "anaphylaxis",
  "swelling of the tongue",
  "swelling of the throat",
  "suicid",
  "brustschmerz",
  "druck auf der brust",
  "atemnot",
  "keine luft",
  "bewusstlos",
  "ohnmächtig",
  "schlaganfall",
  "starke blutung",
  "selbstmord",
  "mich umbringen",
  "anaphylaxie",
  "göğüs ağrısı",
  "göğsümde ağrı",
  "nefes alamıyorum",
  "nefes darlığı",
  "bayıldım",
  "bilinç kaybı",
  "felç",
  "şiddetli kanama",
  "intihar",
  "kendimi öldür",
  "anafilaksi",
  "dolor en el pecho",
  "dolor de pecho",
  "no puedo respirar",
  "dificultad para respirar",
  "falta de aire",
  "me desmayé",
  "pérdida de conciencia",
  "derrame cerebral",
  "sangrado abundante",
  "hemorragia grave",
  "anafilaxia",
  "douleur thoracique",
  "douleur à la poitrine",
  "douleur dans la poitrine",
  "du mal à respirer",
  "pas à respirer",
  "difficulté à respirer",
  "perte de connaissance",
  "évanoui",
  "saignement abondant",
  "hémorragie",
  "choc anaphylactique",
];

// Turkish I/ı/İ do not round-trip through toLowerCase(); fold them so text typed
// in capitals still matches. Mirrors fold() in backend/utils/safety.py.
function foldForMatch(text) {
  return String(text || '').toLowerCase().replace(/i̇/g, 'i').replace(/ı/g, 'i');
}

function checkEmergencySymptoms(text) {
  const haystack = foldForMatch(text);
  const matched = EMERGENCY_PHRASES.filter(p => haystack.includes(foldForMatch(p)));
  return { isEmergency: matched.length > 0, matched };
}

function riskBadgeClass(level) {
  if (level === 'high') return 'bg-red-100 text-red-700';
  if (level === 'medium') return 'bg-yellow-100 text-yellow-700';
  return 'bg-green-100 text-green-700';
}
