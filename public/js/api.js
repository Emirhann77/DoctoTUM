// CareConnect API client — talks to the FastAPI backend (backend/main.py).
// Set window.CARE_API_BASE before loading this script to override the default.
//
// Who the user is travels only in the Authorization header (their Supabase access
// token). No request carries a user id: the backend derives it from the token.
const API_BASE = (typeof window !== 'undefined' && ((window.CARE_CONFIG && window.CARE_CONFIG.apiBase) || window.CARE_API_BASE)) || 'http://localhost:8000';

// Every call resolves to { ok, status, data, error }:
//   status 0   -> the backend could not be reached (pages may fall back or say so)
//   status 401 -> the session is no longer valid; the user is sent to login
//                 (unless options.keepPage is set: the SOS screen must never navigate away)
//   other 4xx  -> the request was refused; `error` is a message that can be shown
async function apiCall(path, options = {}) {
  let authHeader = {};
  if (typeof getAccessToken === 'function') {
    const token = await getAccessToken();
    if (token) authHeader = { Authorization: `Bearer ${token}` };
  }

  const { keepPage, ...fetchOptions } = options;
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      headers: { 'Content-Type': 'application/json', ...authHeader, ...(options.headers || {}) },
    });
  } catch (err) {
    console.warn(`[api] ${path} unreachable`, err.message);
    return { ok: false, status: 0, data: null, error: 'unreachable' };
  }

  let data = null;
  try { data = await res.json(); } catch (e) { /* empty or non-JSON body */ }

  if (res.status === 401) {
    console.warn(`[api] ${path} -> 401, signing out`);
    if (!keepPage && typeof signOut === 'function') signOut();
    return { ok: false, status: 401, data: null, error: 'unauthorized' };
  }
  if (!res.ok) {
    const detail = data && data.detail;
    const message = typeof detail === 'string' ? detail : `HTTP ${res.status}`;
    console.warn(`[api] ${path} -> ${res.status}`, message);
    return { ok: false, status: res.status, data: null, error: message };
  }
  return { ok: true, status: res.status, data, error: null };
}

// Data or null. For reads where "nothing available" is all the caller needs to know.
async function apiFetch(path, options = {}) {
  const result = await apiCall(path, options);
  return result.ok ? result.data : null;
}

function postJson(body) {
  return { method: 'POST', body: JSON.stringify(body) };
}

// ---------- Specialists ----------

async function getSpecialists() {
  return apiFetch('/api/specialists');
}

// ---------- Appointments ----------

// -> apiCall result; data is a list of { id, specialist_id, specialist_name, specialty, start_time, status, reason }
async function listAppointments() {
  return apiCall('/api/appointments');
}

// -> apiCall result (409 = already booked at that time, 422 = invalid time)
async function bookAppointment({ specialistId, startTime, reason = '' }) {
  return apiCall('/api/appointments', postJson({
    specialist_id: String(specialistId),
    start_time: startTime,
    reason,
  }));
}

async function cancelAppointment(appointmentId) {
  return apiCall(`/api/appointments/${encodeURIComponent(appointmentId)}`, { method: 'DELETE' });
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
  return apiFetch('/api/ai_assistant/chat', postJson({
    user_message: message,
    language: typeof CarePrefs !== 'undefined' ? CarePrefs.getLanguage() : undefined,
  }));
}

// ---------- Care Navigator ----------

// input: { symptoms: [slug], description, severity, duration, age, known_conditions }
async function careNavigate(input) {
  return apiFetch('/api/care/navigate', postJson({ ...input, ...preferenceContextPayload() }));
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

// Logs that SOS was pressed. The backend does not contact emergency services
// (`dispatched` is always false) — the page must tell the user to call 112.
async function startEmergency(payload = {}) {
  const body = { symptoms: payload.symptoms || '' };
  if (typeof CarePrefs !== 'undefined') {
    body.preferred_language = CarePrefs.getLanguage();
    const loc = CarePrefs.getLocationForPayload && CarePrefs.getLocationForPayload();
    if (loc) body.location = loc;
  }
  return apiCall('/api/emergency/start', { ...postJson(body), keepPage: true });
}

async function endEmergency(alertId) {
  return apiCall('/api/emergency/end', { ...postJson({ alert_id: alertId }), keepPage: true });
}

// ---------- Prescriptions & pharmacy ----------

// Read-only: prescriptions are issued by a doctor.
async function listPrescriptions() {
  return apiCall('/api/prescriptions');
}

async function listOrders() {
  return apiCall('/api/pharmacy/orders');
}

// items: [{ medication_name, prescription_id?, quantity?, notes? }]
async function createOrders(items) {
  return apiCall('/api/pharmacy/orders', postJson({ items }));
}

async function cancelOrder(orderId) {
  return apiCall(`/api/pharmacy/orders/${encodeURIComponent(orderId)}/cancel`, { method: 'POST' });
}

// ---------- Plans (simulated: nothing is charged) ----------

async function getCurrentPlan() {
  return apiCall('/api/plans/current');
}

async function choosePlan(slug) {
  return apiCall('/api/plans/choose', postJson({ slug }));
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
  "unconscious",
  "not breathing",
  "stopped breathing",
  "seizure",
  "overdose",
  "want to die",
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
  "überdosis",
  "krampfanfall",
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
  "aşırı doz",
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
  "sobredosis",
  "convulsiones",
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
  "surdose",
  "convulsions",
];

// Turkish I/ı/İ do not round-trip through toLowerCase(); fold them so text typed
// in capitals still matches. Mirrors fold() in backend/utils/safety.py.
function foldForMatch(text) {
  return String(text || '').toLowerCase().replace(/i̇/g, 'i').replace(/ı/g, 'i')
    .replace(/[‘’ʼ`´]/g, "'"); // curly apostrophes from phone keyboards
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
