// sos.html
//
// SAFETY: this app does not contact emergency services. Holding the SOS button
// records an alert on the person's account and then puts a real "Call 112" button
// in front of them. Nothing on this page may say or imply that help has been sent.

var HOLD_SECONDS = 3;
var sos = { timer: null, alertId: null, contacts: null, contactsError: false, profile: null };

function sosStatus(text) { document.getElementById('sosStatus').textContent = text; }
function idleText() { return careT('emergency.sosStatusIdle', null, 'Hold the button, then call 112'); }

function startSOS(event) {
  if (event) event.preventDefault();
  if (sos.timer) return;
  var left = HOLD_SECONDS;
  sosStatus(careT('emergency.holding', { seconds: left }, 'Keep holding... ' + left));
  sos.timer = setInterval(function () {
    left--;
    if (left > 0) return sosStatus(careT('emergency.holding', { seconds: left }, 'Keep holding... ' + left));
    clearInterval(sos.timer);
    sos.timer = null;
    triggerEmergency();
  }, 1000);
}

function cancelHold() {
  if (!sos.timer) return;
  clearInterval(sos.timer);
  sos.timer = null;
  sosStatus(idleText());
}

async function triggerEmergency() {
  sosStatus(idleText());
  // Show the call screen immediately: it must not wait on the network.
  document.getElementById('sosLogNote').textContent = '';
  document.getElementById('sosOverlay').classList.remove('hidden');
  document.getElementById('sosCallBtn').focus();

  var result = await startEmergency({ symptoms: 'SOS button' });
  if (result.ok) {
    sos.alertId = result.data.alert_id;
    document.getElementById('sosLogNote').textContent = careT('emergency.logged', null, 'This alert was saved to your account.');
  } else {
    document.getElementById('sosLogNote').textContent = careT('emergency.notLogged', null, 'The alert could not be saved. Call now anyway.');
  }
}

async function closeEmergency() {
  document.getElementById('sosOverlay').classList.add('hidden');
  if (sos.alertId) {
    var id = sos.alertId;
    sos.alertId = null;
    await endEmergency(id);
  }
}

// ---- Medical ID --------------------------------------------------------------

function renderMedicalId() {
  var p = sos.profile;
  var set = function (id, value) { document.getElementById(id).textContent = value || '—'; };
  if (!p) return;
  var medical = p.medical || {};
  set('midName', p.displayName);
  set('midDob', medical.date_of_birth ? formatDate(medical.date_of_birth + 'T12:00:00') : '');
  set('midBlood', medical.blood_type);
  set('midWeight', medical.weight_kg ? Number(medical.weight_kg) + ' kg' : '');
  set('midAllergies', p.allergies.map(function (a) { return a.label; }).join(', '));
  set('midConditions', p.conditions.map(function (c) { return c.label; }).join(', '));
}

// ---- Contacts ----------------------------------------------------------------

function renderContacts() {
  var box = document.getElementById('contactsList');
  if (sos.contactsError) return void (box.innerHTML = stateBlockHTML('cloud_off', careT('common.failed', null, 'That did not work. Please try again.')));
  if (!sos.contacts) return void (box.innerHTML = stateBlockHTML('hourglass_empty', careT('common.loading', null, 'Loading...')));
  if (!sos.contacts.length)
    return void (box.innerHTML = stateBlockHTML('group_add', careT('emergency.noContacts', null, 'Add someone to call in an emergency.')));
  box.innerHTML = sos.contacts.map(function (c) {
    var tel = String(c.phone).replace(/[^0-9+]/g, '');
    return '<div class="px-5 py-4 flex items-center gap-3">' +
      '<div class="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center shrink-0"><span class="material-symbols-outlined text-slate-400" style="font-variation-settings:\'FILL\' 1" aria-hidden="true">person</span></div>' +
      '<div class="flex-1 min-w-0"><p class="font-medium text-sm">' + escapeHtml(c.name) + '</p>' +
      '<p class="text-xs text-on-surface-variant">' + escapeHtml([c.relationship, c.phone].filter(Boolean).join(' · ')) + '</p></div>' +
      '<a href="tel:' + escapeHtml(tel) + '" class="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center hover:bg-green-200" aria-label="' + escapeHtml(careT('emergency.callName', { name: c.name }, 'Call ' + c.name)) + '">' +
        '<span class="material-symbols-outlined text-secondary text-base" style="font-variation-settings:\'FILL\' 1" aria-hidden="true">call</span></a>' +
      '<button type="button" data-remove-contact="' + escapeHtml(c.id) + '" class="w-10 h-10 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-100" aria-label="' + escapeHtml(careT('profile.remove', { name: c.name }, 'Remove ' + c.name)) + '">' +
        '<span class="material-symbols-outlined text-base" aria-hidden="true">delete</span></button>' +
    '</div>';
  }).join('');
}

async function loadContacts() {
  var result = await CareRecords.listContacts();
  sos.contactsError = !result.ok;
  sos.contacts = result.ok ? result.data : null;
  renderContacts();
}

async function addContact(event) {
  event.preventDefault();
  var form = event.target;
  var result = await CareRecords.addContact({
    name: document.getElementById('contactName').value,
    phone: document.getElementById('contactPhone').value,
    relationship: document.getElementById('contactRelation').value,
  });
  if (!result.ok) return showToast(careT('emergency.contactInvalid', null, 'Could not save. Check the name and phone number.'), 'error');
  form.reset();
  document.getElementById('contactForm').classList.add('hidden');
  loadContacts();
}

document.addEventListener('DOMContentLoaded', async function () {
  var session = await requireAuth();
  if (!session) return;
  sosStatus(idleText());
  renderContacts();
  window.addEventListener('careconnect:redraw-dynamic', function () {
    if (!sos.timer) sosStatus(idleText());
    renderContacts();
    renderMedicalId();
  });

  var btn = document.getElementById('sosBtn');
  btn.addEventListener('pointerdown', startSOS);
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (name) { btn.addEventListener(name, cancelHold); });
  // Keyboard: holding Space/Enter works like a press; a keyboard user is not asked to hold a pointer.
  btn.addEventListener('keydown', function (e) { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) startSOS(e); });
  btn.addEventListener('keyup', function (e) { if (e.key === ' ' || e.key === 'Enter') cancelHold(); });
  btn.addEventListener('contextmenu', function (e) { e.preventDefault(); });

  document.getElementById('sosCloseBtn').addEventListener('click', closeEmergency);
  document.getElementById('contactAdd').addEventListener('click', function () {
    document.getElementById('contactForm').classList.toggle('hidden');
    document.getElementById('contactName').focus();
  });
  document.getElementById('contactForm').addEventListener('submit', addContact);
  document.getElementById('contactsList').addEventListener('click', async function (e) {
    var remove = e.target.closest('[data-remove-contact]');
    if (!remove) return;
    await CareRecords.removeContact(remove.getAttribute('data-remove-contact'));
    loadContacts();
  });

  loadContacts();
  CareRecords.getProfile().then(function (result) {
    if (result.ok) { sos.profile = result.data; renderMedicalId(); }
  });
});
