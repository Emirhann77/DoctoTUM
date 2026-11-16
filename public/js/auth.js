// Supabase auth client — shared across all HTML pages
// Reads keys injected by each page via window.SUPABASE_URL / window.SUPABASE_ANON_KEY
// or falls back to the hardcoded project values below.

const SUPABASE_URL  = window.SUPABASE_URL  || 'https://rfuwggnimjzlrdygbjqw.supabase.co';
const SUPABASE_ANON = window.SUPABASE_ANON || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJmdXdnZ25pbWp6bHJkeWdianF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc3MTcwMjAsImV4cCI6MjA5MzI5MzAyMH0.EhDjjD6PqjwcXjygBm-xjLFhdF5N25EE8QLqTelrFd8';

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
      emailRedirectTo: `${location.origin}/verify.html`,
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
    redirectTo: `${location.origin}/reset-password.html`,
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
