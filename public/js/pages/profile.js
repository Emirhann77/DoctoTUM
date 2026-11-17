// profile.html — the signed-in person's own details, read and saved through
// js/records.js (Supabase, row-level security), plus their plan from the backend.

var profile = { data: null, error: false, plan: null, counts: { appointments: null, medications: null } };

function setText(id, value) {
  document.getElementById(id).textContent = value == null || value === '' ? '—' : value;
}

function bodyText(medical) {
  var parts = [];
  if (medical && medical.height_cm) parts.push(Number(medical.height_cm) + ' cm');
  if (medical && medical.weight_kg) parts.push(Number(medical.weight_kg) + ' kg');
  return parts.join(' · ');
}

function chipListHTML(items, removeAttr, emptyText, tone) {
  if (!items.length) return '<p class="text-sm text-on-surface-variant">' + escapeHtml(emptyText) + '</p>';
  return '<div class="flex flex-wrap gap-2">' + items.map(function (item) {
    return '<span class="inline-flex items-center gap-1 text-xs font-medium pl-3 pr-1 py-1 rounded-full ' + tone + '">' + escapeHtml(item.label) +
      '<button type="button" ' + removeAttr + '="' + escapeHtml(item.id) + '" class="w-6 h-6 rounded-full flex items-center justify-center hover:bg-black/10" aria-label="' +
      escapeHtml(careT('profile.remove', { name: item.label }, 'Remove ' + item.label)) + '"><span class="material-symbols-outlined text-sm" aria-hidden="true">close</span></button></span>';
  }).join('') + '</div>';
}

function renderProfile() {
  var d = profile.data;
  var loadingText = profile.error
    ? careT('common.failed', null, 'That did not work. Please try again.')
    : careT('common.loading', null, 'Loading...');
  if (!d) {
    document.getElementById('conditionsList').innerHTML = '<p class="text-sm text-on-surface-variant">' + escapeHtml(loadingText) + '</p>';
    document.getElementById('allergiesList').innerHTML = '<p class="text-sm text-on-surface-variant">' + escapeHtml(loadingText) + '</p>';
    return;
  }
  var medical = d.medical || {};
  document.getElementById('profileName').textContent = d.displayName || d.email;
  document.getElementById('profileEmail').textContent = d.email;
  document.getElementById('profileAvatar').textContent =
    String(d.displayName || d.email).trim().split(/\s+/).map(function (w) { return w.charAt(0); }).join('').slice(0, 2).toUpperCase();
  setText('infoDob', medical.date_of_birth ? formatDate(medical.date_of_birth + 'T12:00:00') : '');
  setText('infoBlood', medical.blood_type);
  setText('infoBody', bodyText(medical));
  setText('infoPhone', medical.phone);
  setText('statConditions', d.conditions.length);
  setText('statAppointments', profile.counts.appointments);
  setText('statMedications', profile.counts.medications);

  document.getElementById('conditionsList').innerHTML =
    chipListHTML(d.conditions, 'data-remove-condition', careT('profile.noConditions', null, 'None recorded.'), 'bg-blue-100 text-blue-800');
  document.getElementById('allergiesList').innerHTML =
    chipListHTML(d.allergies, 'data-remove-allergy', careT('profile.noAllergies', null, 'None recorded.'), 'bg-red-100 text-red-700');

  var plan = profile.plan;
  document.getElementById('planName').textContent = plan ? plan.name : careT('profile.noPlan', null, 'No plan selected');
  document.getElementById('planPrice').textContent = plan ? '$' + Math.round(plan.price_cents_monthly / 100) + '/mo' : '';
  document.getElementById('planPrice').classList.toggle('hidden', !plan);
  document.getElementById('profilePlanBadge').textContent = plan ? plan.name : '';
  document.getElementById('profilePlanBadge').classList.toggle('hidden', !plan);
}

async function loadProfile() {
  var result = await CareRecords.getProfile();
  profile.error = !result.ok;
  if (result.ok) profile.data = result.data;
  renderProfile();
}

function openEdit() {
  var d = profile.data;
  if (!d) return;
  var medical = d.medical || {};
  document.getElementById('editName').value = d.displayName || '';
  document.getElementById('editDob').value = medical.date_of_birth || '';
  document.getElementById('editBlood').value = medical.blood_type || '';
  document.getElementById('editPhone').value = medical.phone || '';
  document.getElementById('editHeight').value = medical.height_cm || '';
  document.getElementById('editWeight').value = medical.weight_kg || '';
  document.getElementById('editDob').max = new Date().toISOString().slice(0, 10);
  document.getElementById('editModal').classList.remove('hidden');
  document.getElementById('editName').focus();
}

async function saveEdit(event) {
  event.preventDefault();
  var btn = document.getElementById('editSave');
  btn.disabled = true;
  var result = await CareRecords.saveProfile({
    displayName: document.getElementById('editName').value,
    dateOfBirth: document.getElementById('editDob').value,
    bloodType: document.getElementById('editBlood').value,
    phone: document.getElementById('editPhone').value,
    heightCm: document.getElementById('editHeight').value,
    weightKg: document.getElementById('editWeight').value,
  });
  btn.disabled = false;
  if (!result.ok) return showToast(careT('common.failed', null, 'That did not work. Please try again.'), 'error');
  document.getElementById('editModal').classList.add('hidden');
  showToast(careT('profile.savedProfile', null, 'Profile saved.'));
  loadProfile();
}

async function addFromForm(event, inputId, add) {
  event.preventDefault();
  var input = document.getElementById(inputId);
  var label = input.value.trim();
  if (!label) return;
  var result = await add(label);
  if (!result.ok) return showToast(careT('common.failed', null, 'That did not work. Please try again.'), 'error');
  input.value = '';
  loadProfile();
}

async function removeItem(remove, id) {
  var result = await remove(id);
  if (!result.ok) showToast(careT('common.failed', null, 'That did not work. Please try again.'), 'error');
  loadProfile();
}

document.addEventListener('DOMContentLoaded', async function () {
  var session = await requireAuth();
  if (!session) return;
  document.getElementById('profileName').textContent = firstName(session);
  document.getElementById('profileEmail').textContent = session.user.email || '';
  renderProfile();
  window.addEventListener('careconnect:redraw-dynamic', renderProfile);

  document.getElementById('editOpen').addEventListener('click', openEdit);
  document.getElementById('editForm').addEventListener('submit', saveEdit);
  document.getElementById('conditionForm').addEventListener('submit', function (e) { addFromForm(e, 'conditionInput', CareRecords.addCondition); });
  document.getElementById('allergyForm').addEventListener('submit', function (e) { addFromForm(e, 'allergyInput', CareRecords.addAllergy); });
  document.getElementById('conditionsList').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-remove-condition]');
    if (btn) removeItem(CareRecords.removeCondition, btn.getAttribute('data-remove-condition'));
  });
  document.getElementById('allergiesList').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-remove-allergy]');
    if (btn) removeItem(CareRecords.removeAllergy, btn.getAttribute('data-remove-allergy'));
  });

  loadProfile();
  Promise.all([listAppointments(), listPrescriptions(), getCurrentPlan()]).then(function (r) {
    var now = Date.now();
    profile.counts.appointments = r[0].ok ? r[0].data.filter(function (a) { return new Date(a.start_time).getTime() >= now; }).length : null;
    profile.counts.medications = r[1].ok ? r[1].data.length : null;
    profile.plan = r[2].ok ? r[2].data : null;
    renderProfile();
  });
});
