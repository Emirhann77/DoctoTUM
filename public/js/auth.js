// Supabase auth client — shared across all HTML pages
// Reads window.SUPABASE_URL / window.SUPABASE_ANON if a page sets them, otherwise the
// project values below. Both are public by design (the anon key only grants what
// row-level security allows); the service-role key must never appear in this folder.

const SUPABASE_URL  = window.SUPABASE_URL  || 'https://fzhoelaooktqryndsuie.supabase.co';
const SUPABASE_ANON = window.SUPABASE_ANON || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ6aG9lbGFvb2t0cXJ5bmRzdWllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTQ4NjY3NTMsImV4cCI6MjExMDQ0Mjc1M30.RlJkIfmQMjumSSZMTxaQWxN2uMItTTGIPOT5GvVov64';

// Supabase JS v2 loaded via CDN (added by each page via <script> tag)
let _supabase = null;
function getSupabase() {
  if (!_supabase) {
    if (typeof supabase === 'undefined') {
      console.error('[auth] Supabase CDN not loaded. Add the CDN <script> before auth.js.');
      return null;
    }
    _supabase = supabase.createClient(SUPABASE_URL, SUPABASE_ANON, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
    });
  }
  return _supabase;
}

// Returns the active session or null
async function getSession() {
  const client = getSupabase();
  if (!client) return null;
  const { data: { session } } = await client.auth.getSession();
  return session;
}

// Returns the logged-in user object or null
async function getUser() {
  const session = await getSession();
  return session ? session.user : null;
}

// Redirects to login if no valid session. Returns session on success.
async function requireAuth(redirectTo = 'login.html') {
  const session = await getSession();
  if (!session) {
    window.location.href = redirectTo;
    return null;
  }
  return session;
}

// Sign up with email + password + full name
async function signUp(email, password, fullName) {
  const client = getSupabase();
  const { data, error } = await client.auth.signUp({
    email,
    password,
    options: {
      data: { full_name: fullName },
      emailRedirectTo: `${(window.CARE_CONFIG && window.CARE_CONFIG.webOrigin) || location.origin}/verify.html`,
    },
  });
  return { data, error };
}

// Sign in with email + password
async function signIn(email, password) {
  const client = getSupabase();
  const { data, error } = await client.auth.signInWithPassword({ email, password });
  return { data, error };
}

// Sign out
async function signOut() {
  const client = getSupabase();
  await client.auth.signOut();
  window.location.href = 'login.html';
}

// Send password reset email
async function sendPasswordReset(email) {
  const client = getSupabase();
  const { error } = await client.auth.resetPasswordForEmail(email, {
    redirectTo: `${(window.CARE_CONFIG && window.CARE_CONFIG.webOrigin) || location.origin}/reset-password.html`,
  });
  return { error };
}

// Update password (called from reset-password page after redirect)
async function updatePassword(newPassword) {
  const client = getSupabase();
  const { error } = await client.auth.updateUser({ password: newPassword });
  return { error };
}

// Resend verification email
async function resendVerification(email) {
  const client = getSupabase();
  const { error } = await client.auth.resend({ type: 'signup', email });
  return { error };
}

// Returns the JWT access token for API calls
async function getAccessToken() {
  const session = await getSession();
  return session ? session.access_token : null;
}
