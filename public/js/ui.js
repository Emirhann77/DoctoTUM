// Small helpers shared by the pages. Plain globals; load after js/i18n/*.

// For text placed into innerHTML or an HTML attribute.
function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Translated string with an English fallback for when the key is missing.
function careT(key, vars, fallback) {
  if (typeof CareI18n === 'undefined') return fallback || key;
  var text = CareI18n.t(key, vars);
  return text === key && fallback ? fallback : text;
}

function careLocale() {
  return typeof CarePrefs !== 'undefined' ? CarePrefs.getLanguage() : 'en';
}

// "Wed, 18 Nov, 14:00" in the interface language.
function formatDateTime(iso) {
  var d = new Date(iso);
  if (isNaN(d)) return '';
  return d.toLocaleString(careLocale(), { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function formatDate(iso) {
  var d = new Date(iso);
  if (isNaN(d)) return '';
  return d.toLocaleDateString(careLocale(), { day: 'numeric', month: 'short', year: 'numeric' });
}

// A brief message at the bottom of the screen. kind: 'ok' | 'error'.
function showToast(message, kind) {
  var host = document.getElementById('careToast');
  if (!host) {
    host = document.createElement('div');
    host.id = 'careToast';
    host.setAttribute('role', 'status');
    host.setAttribute('aria-live', 'polite');
    host.className = 'fixed left-1/2 -translate-x-1/2 bottom-24 z-[60] max-w-[90vw] px-4 py-3 rounded-2xl text-sm font-medium shadow-lg hidden';
    document.body.appendChild(host);
  }
  host.textContent = message;
  host.classList.remove('hidden', 'bg-slate-900', 'bg-error', 'text-white');
  host.classList.add(kind === 'error' ? 'bg-error' : 'bg-slate-900', 'text-white');
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(function () { host.classList.add('hidden'); }, kind === 'error' ? 6000 : 3500);
}

// Placeholder block for a list with nothing in it, or one that failed to load.
function stateBlockHTML(icon, text) {
  return '<div class="flex flex-col items-center text-center gap-2 py-8 px-4 text-on-surface-variant">' +
    '<span class="material-symbols-outlined text-3xl text-slate-300" aria-hidden="true">' + escapeHtml(icon) + '</span>' +
    '<p class="text-sm">' + escapeHtml(text) + '</p></div>';
}

// The right message for a failed apiCall(): unreachable vs refused.
function apiErrorText(result) {
  if (!result || result.status === 0) return careT('common.offline', null, 'Could not reach the server. Check your connection and try again.');
  if (result.status === 503) return careT('common.unavailable', null, 'The service is temporarily unavailable. Please try again.');
  return careT('common.failed', null, 'That did not work. Please try again.');
}

function firstName(session) {
  var meta = (session && session.user && session.user.user_metadata) || {};
  var email = (session && session.user && session.user.email) || '';
  return meta.full_name || email.split('@')[0] || '';
}
