// pharmacy.html — prescriptions issued to this person, and their pharmacy orders.
// Ordering records a request with the pharmacy; prices shown are indicative and
// NO PAYMENT IS TAKEN (payments are not connected in this build).

var pharmacy = { prescriptions: null, orders: null, rxError: null, ordersError: null, cart: [] };

var ORDER_STATUS = {
  requested: { key: 'pharmacy.status.requested', fallback: 'Requested', css: 'bg-blue-100 text-primary' },
  processing: { key: 'pharmacy.status.processing', fallback: 'Being prepared', css: 'bg-yellow-100 text-yellow-700' },
  shipped: { key: 'pharmacy.status.shipped', fallback: 'On its way', css: 'bg-green-100 text-green-700' },
  cancelled: { key: 'pharmacy.status.cancelled', fallback: 'Cancelled', css: 'bg-slate-100 text-slate-500' },
};

function renderPrescriptions() {
  var box = document.getElementById('rxList');
  if (pharmacy.rxError) return void (box.innerHTML = stateBlockHTML('cloud_off', apiErrorText(pharmacy.rxError)));
  if (!pharmacy.prescriptions) return void (box.innerHTML = stateBlockHTML('hourglass_empty', careT('common.loading', null, 'Loading...')));
  if (!pharmacy.prescriptions.length)
    return void (box.innerHTML = stateBlockHTML('medication', careT('pharmacy.noPrescriptions', null, 'No prescriptions yet. A doctor adds them after a consultation.')));
  box.innerHTML = pharmacy.prescriptions.map(function (rx) {
    return '<div class="bg-surface-container-lowest rounded-2xl border border-slate-100 p-4 shadow-sm">' +
      '<div class="flex items-start justify-between gap-3 mb-3"><div class="flex items-center gap-3 min-w-0">' +
        '<div class="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center shrink-0"><span class="material-symbols-outlined text-secondary" style="font-variation-settings:\'FILL\' 1" aria-hidden="true">medication</span></div>' +
        '<div class="min-w-0"><p class="font-semibold text-sm">' + escapeHtml(rx.medication) + '</p>' +
        (rx.prescribed_by ? '<p class="text-xs text-on-surface-variant">' + escapeHtml(careT('pharmacy.prescribedBy', { name: rx.prescribed_by }, 'Prescribed by ' + rx.prescribed_by)) + '</p>' : '') +
      '</div></div></div>' +
      '<p class="text-xs text-on-surface-variant mb-3">' + escapeHtml([rx.dosage, rx.instructions].filter(Boolean).join(' · ')) + '</p>' +
      '<button type="button" data-refill="' + escapeHtml(rx.id) + '" class="w-full bg-secondary text-white text-xs font-semibold py-2.5 rounded-full hover:opacity-90">' +
        escapeHtml(careT('pharmacy.requestRefill', null, 'Request refill')) + '</button></div>';
  }).join('');
}

function renderOrders() {
  var box = document.getElementById('orderList');
  if (pharmacy.ordersError) return void (box.innerHTML = stateBlockHTML('cloud_off', apiErrorText(pharmacy.ordersError)));
  if (!pharmacy.orders) return void (box.innerHTML = stateBlockHTML('hourglass_empty', careT('common.loading', null, 'Loading...')));
  if (!pharmacy.orders.length)
    return void (box.innerHTML = stateBlockHTML('local_shipping', careT('pharmacy.noOrders', null, 'No orders yet.')));
  box.innerHTML = pharmacy.orders.map(function (o) {
    var st = ORDER_STATUS[o.status] || ORDER_STATUS.requested;
    return '<div class="px-5 py-4 flex items-center gap-3">' +
      '<div class="flex-1 min-w-0"><p class="font-medium text-sm">' + escapeHtml(o.medication_name) + (o.quantity > 1 ? ' × ' + Number(o.quantity) : '') + '</p>' +
      '<p class="text-xs text-on-surface-variant">' + escapeHtml(formatDate(o.created_at)) + (o.notes ? ' · ' + escapeHtml(o.notes) : '') + '</p></div>' +
      '<span class="text-xs px-2 py-1 rounded-full font-medium ' + st.css + '">' + escapeHtml(careT(st.key, null, st.fallback)) + '</span>' +
      (o.status === 'requested'
        ? '<button type="button" data-cancel-order="' + escapeHtml(o.id) + '" class="text-xs font-semibold text-error px-2 py-1.5 rounded-full hover:bg-red-50">' + escapeHtml(careT('pharmacy.cancelOrder', null, 'Cancel')) + '</button>'
        : '') +
    '</div>';
  }).join('');
}

function renderCart() {
  var count = pharmacy.cart.reduce(function (n, i) { return n + i.quantity; }, 0);
  document.getElementById('cartBanner').classList.toggle('hidden', !count);
  document.getElementById('cartText').textContent = careT('pharmacy.cartCount', { count: count }, count + ' in your request');
}

function addToCart(item) {
  var same = pharmacy.cart.find(function (i) { return i.medication_name === item.medication_name && i.prescription_id === item.prescription_id; });
  if (same) same.quantity = Math.min(10, same.quantity + 1);
  else pharmacy.cart.push({ medication_name: item.medication_name, prescription_id: item.prescription_id || null, quantity: 1 });
  renderCart();
}

async function loadPharmacy() {
  var results = await Promise.all([listPrescriptions(), listOrders()]);
  pharmacy.rxError = results[0].ok ? null : results[0];
  pharmacy.prescriptions = results[0].ok ? results[0].data : null;
  pharmacy.ordersError = results[1].ok ? null : results[1];
  pharmacy.orders = results[1].ok ? results[1].data : null;
  renderPrescriptions();
  renderOrders();
}

async function submitOrder(items) {
  var result = await createOrders(items);
  if (!result.ok) { showToast(apiErrorText(result), 'error'); return false; }
  showToast(careT('pharmacy.orderPlaced', null, 'Request sent to the pharmacy. No payment was taken.'));
  await loadPharmacy();
  return true;
}

async function checkout() {
  if (!pharmacy.cart.length) return;
  var btn = document.getElementById('checkoutBtn');
  btn.disabled = true;
  var ok = await submitOrder(pharmacy.cart.map(function (i) {
    var item = { medication_name: i.medication_name, quantity: i.quantity };
    if (i.prescription_id) item.prescription_id = i.prescription_id;
    return item;
  }));
  btn.disabled = false;
  if (ok) { pharmacy.cart = []; renderCart(); }
}

async function submitMedicationRequest(event) {
  event.preventDefault();
  var name = document.getElementById('requestName').value.trim();
  var note = document.getElementById('requestNote').value.trim();
  if (!name) return;
  var item = { medication_name: name, quantity: 1 };
  if (note) item.notes = note;
  if (await submitOrder([item])) {
    event.target.reset();
    document.getElementById('newRxModal').classList.add('hidden');
  }
}

async function onCancelOrder(id) {
  var result = await cancelOrder(id);
  if (result.ok) showToast(careT('pharmacy.orderCancelled', null, 'Order cancelled.'));
  else if (result.status === 409) showToast(careT('pharmacy.orderTooLate', null, 'This order is already being prepared and can no longer be cancelled.'), 'error');
  else showToast(apiErrorText(result), 'error');
  loadPharmacy();
}

document.addEventListener('DOMContentLoaded', async function () {
  var session = await requireAuth();
  if (!session) return;
  renderPrescriptions();
  renderOrders();
  renderCart();
  window.addEventListener('careconnect:redraw-dynamic', function () { renderPrescriptions(); renderOrders(); renderCart(); });

  document.getElementById('rxList').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-refill]');
    if (!btn) return;
    var rx = (pharmacy.prescriptions || []).find(function (p) { return p.id === btn.dataset.refill; });
    if (rx) addToCart({ medication_name: rx.medication, prescription_id: rx.id });
  });
  document.getElementById('otcList').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-otc]');
    if (btn) addToCart({ medication_name: btn.dataset.otc });
  });
  document.getElementById('orderList').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-cancel-order]');
    if (btn) onCancelOrder(btn.dataset.cancelOrder);
  });
  document.getElementById('checkoutBtn').addEventListener('click', checkout);
  document.getElementById('requestForm').addEventListener('submit', submitMedicationRequest);
  loadPharmacy();
});
