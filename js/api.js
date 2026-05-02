// CareConnect API client — talks to the FastAPI backend (backend/main.py)
// Set window.CARE_API_BASE before loading this script to override the default.
const API_BASE = (typeof window !== 'undefined' && window.CARE_API_BASE) || 'http://localhost:8000';

// Demo user — replace with real auth session once Supabase auth is wired up
const DEMO_USER_ID = 1;

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
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

async function getAppointments(userId = DEMO_USER_ID) {
  return apiFetch(`/api/appointments?user_id=${userId}`);
}

async function bookAppointment({ specialistId, startTime, reason = '' }) {
  return apiFetch('/api/appointments', {
    method: 'POST',
    body: JSON.stringify({
      user_id: DEMO_USER_ID,
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

async function aiChat(message, userId = DEMO_USER_ID) {
  return apiFetch('/api/ai_assistant/chat', {
    method: 'POST',
    body: JSON.stringify({ user_message: message, user_id: userId }),
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

// ---------- Emergency ----------

async function startEmergency(symptoms = '') {
  return apiFetch('/api/emergency/start', {
    method: 'POST',
    body: JSON.stringify({ user_id: DEMO_USER_ID, symptoms }),
  });
}

async function endEmergency(sessionId) {
  return apiFetch('/api/emergency/end', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  });
}

// ---------- Prescriptions ----------

async function getPrescriptions(userId = DEMO_USER_ID) {
  return apiFetch(`/api/prescriptions?user_id=${userId}`);
}

async function createPrescription({ medication, dosage, instructions, prescribedBy }) {
  return apiFetch('/api/prescriptions', {
    method: 'POST',
    body: JSON.stringify({
      user_id: DEMO_USER_ID,
      medication,
      dosage,
      instructions,
      prescribed_by: prescribedBy,
    }),
  });
}

// ---------- Risk level helpers (mirrors backend/utils/safety.py) ----------

const EMERGENCY_PHRASES = [
  'chest pain','pressure in my chest','difficulty breathing',
  'can\'t breathe','cant breathe','shortness of breath',
  'loss of consciousness','passed out','fainted','stroke',
  'face drooping','arm weakness','slurred speech',
  'severe bleeding','bleeding heavily','suicidal',
  'suicidal thoughts','kill myself','self harm',
  'severe allergic reaction','anaphylaxis',
  'swelling of the tongue','swelling of the throat',
];

function checkEmergencySymptoms(text) {
  const lower = (text || '').toLowerCase();
  const matched = EMERGENCY_PHRASES.filter(p => lower.includes(p));
  return { isEmergency: matched.length > 0, matched };
}

function riskBadgeClass(level) {
  if (level === 'high') return 'bg-red-100 text-red-700';
  if (level === 'medium') return 'bg-yellow-100 text-yellow-700';
  return 'bg-green-100 text-green-700';
}
