// index.html — the signed-in person's own appointments, medications and orders.
// Vitals, health score and lab results on this page are sample data and are labelled so.

var homeData = { appointments: null, prescriptions: null, orders: null, plan: null, appointmentsError: null, prescriptionsError: null };

function initialsOf(name) {
  return String(name || '').trim().split(/\s+/).map(function (w) { return w.charAt(0); }).join('').slice(0, 2).toUpperCase() || '?';
}

function upcoming(appointments) {
  var now = Date.now();
  return (appointments || []).filter(function (a) { return new Date(a.start_time).getTime() >= now - 3600000; });
}

function renderHomeHeader(session) {
  var name = firstName(session);
  document.getElementById('homeName').textContent = name;
  document.getElementById('homeAvatar').textContent = initialsOf(name);
  var today = new Date().toLocaleDateString(careLocale(), { weekday: 'long', day: 'numeric', month: 'long' });
  document.getElementById('homeDate').textContent = homeData.plan ? today + ' · ' + homeData.plan.name : today;
}

function renderNextAppointment() {
  var box = document.getElementById('nextAppointment');
  if (homeData.appointmentsError) return void (box.innerHTML = stateBlockHTML('cloud_off', apiErrorText(homeData.appointmentsError)));
  if (!homeData.appointments) return void (box.innerHTML = stateBlockHTML('hourglass_empty', careT('common.loading', null, 'Loading...')));
  var next = upcoming(homeData.appointments)[0];
  if (!next) {
    box.innerHTML = '<div class="p-5 flex items-center gap-4">' +
      '<div class="w-12 h-12 bg-blue-50 rounded-2xl flex items-center justify-center shrink-0"><span class="material-symbols-outlined text-primary" aria-hidden="true">event_available</span></div>' +
      '<p class="flex-1 text-sm text-on-surface-variant">' + escapeHtml(careT('home.noAppointment', null, 'Nothing booked yet.')) + '</p>' +
      '<a href="consult.html" class="bg-primary text-white text-sm font-medium px-4 py-2 rounded-full hover:bg-blue-800 transition-colors">' + escapeHtml(careT('home.bookVisit', null, 'Book Visit')) + '</a></div>';
    return;
  }
  box.innerHTML = '<div class="p-5 flex items-center gap-4">' +
    '<div class="w-14 h-14 rounded-2xl bg-primary-fixed text-on-primary-fixed flex items-center justify-center font-bold shrink-0" aria-hidden="true">' +
      escapeHtml(initialsOf(String(next.specialist_name || '').replace(/^(dr|prof)\.?\s+/i, ''))) + '</div>' +
    '<div class="flex-1 min-w-0">' +
      '<p class="font-semibold text-on-surface">' + escapeHtml(next.specialist_name || '') + '</p>' +
      '<p class="text-sm text-on-surface-variant">' + escapeHtml(next.specialty || '') + '</p>' +
      '<div class="flex items-center gap-2 mt-2"><span class="material-symbols-outlined text-sm text-primary" aria-hidden="true">calendar_today</span>' +
      '<span class="text-sm text-primary font-medium">' + escapeHtml(formatDateTime(next.start_time)) + '</span></div>' +
    '</div></div>';
}

function renderMeds() {
  var box = document.getElementById('medsToday');
  if (homeData.prescriptionsError) return void (box.innerHTML = stateBlockHTML('cloud_off', apiErrorText(homeData.prescriptionsError)));
  if (!homeData.prescriptions) return void (box.innerHTML = stateBlockHTML('hourglass_empty', careT('common.loading', null, 'Loading...')));
  if (!homeData.prescriptions.length)
    return void (box.innerHTML = stateBlockHTML('medication', careT('home.noMedications', null, 'No active prescriptions.')));
  box.innerHTML = homeData.prescriptions.map(function (rx) {
    return '<div class="px-5 py-4 flex items-center gap-4">' +
      '<div class="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center shrink-0"><span class="material-symbols-outlined text-secondary text-xl" style="font-variation-settings:\'FILL\' 1" aria-hidden="true">medication</span></div>' +
      '<div class="flex-1 min-w-0"><p class="font-medium text-sm">' + escapeHtml(rx.medication) + '</p>' +
      '<p class="text-xs text-on-surface-variant">' + escapeHtml([rx.dosage, rx.instructions].filter(Boolean).join(' · ')) + '</p></div></div>';
  }).join('');
}

function renderStats() {
  var set = function (id, list) { document.getElementById(id).textContent = list ? String(list.length) : '–'; };
  set('statAppointments', homeData.appointments && upcoming(homeData.appointments));
  set('statMedications', homeData.prescriptions);
  set('statOrders', homeData.orders && homeData.orders.filter(function (o) { return o.status === 'requested' || o.status === 'processing'; }));
}

function renderNotifications() {
  var items = [];
  var next = homeData.appointments && upcoming(homeData.appointments)[0];
  if (next) items.push({ icon: 'event', color: 'text-primary', title: careT('home.notifAppointment', null, 'Upcoming appointment'),
    detail: [next.specialist_name, formatDateTime(next.start_time)].filter(Boolean).join(' · ') });
  (homeData.orders || []).filter(function (o) { return o.status === 'requested' || o.status === 'processing'; }).slice(0, 3).forEach(function (o) {
    items.push({ icon: 'local_shipping', color: 'text-secondary', title: careT('home.notifOrder', null, 'Pharmacy order in progress'), detail: o.medication_name });
  });
  document.getElementById('notifDot').classList.toggle('hidden', !items.length);
  document.getElementById('notifList').innerHTML = items.length
    ? items.map(function (n) {
        return '<div class="p-4 flex gap-3"><span class="material-symbols-outlined ' + n.color + ' mt-0.5" style="font-variation-settings:\'FILL\' 1" aria-hidden="true">' + n.icon + '</span>' +
          '<div><p class="text-sm font-medium">' + escapeHtml(n.title) + '</p><p class="text-xs text-on-surface-variant">' + escapeHtml(n.detail) + '</p></div></div>';
      }).join('')
    : stateBlockHTML('notifications_off', careT('home.noNotifications', null, 'No notifications.'));
}

function renderHome(session) {
  renderHomeHeader(session);
  renderNextAppointment();
  renderMeds();
  renderStats();
  renderNotifications();
}

document.addEventListener('DOMContentLoaded', async function () {
  var session = await requireAuth();
  if (!session) return;
  renderHome(session);
  window.addEventListener('careconnect:redraw-dynamic', function () { renderHome(session); });

  var results = await Promise.all([listAppointments(), listPrescriptions(), listOrders(), getCurrentPlan()]);
  homeData.appointmentsError = results[0].ok ? null : results[0];
  homeData.prescriptionsError = results[1].ok ? null : results[1];
  homeData.appointments = results[0].ok ? results[0].data : null;
  homeData.prescriptions = results[1].ok ? results[1].data : null;
  homeData.orders = results[2].ok ? results[2].data : null;
  homeData.plan = results[3].ok ? results[3].data : null;
  renderHome(session);
});
