// plans.html — DEMO billing. Choosing a plan records it on the account through the
// backend; no payment is taken. Replace with a real checkout before charging anyone.

var billing = 'monthly';
var currentPlanSlug = null;

function setBilling(type) {
  billing = type;
  var isAnnual = type === 'annual';
  document.getElementById('monthlyBtn').className = 'px-5 py-2 rounded-full ' + (!isAnnual ? 'bg-primary text-white' : 'text-on-surface') + ' text-sm font-semibold transition-all';
  document.getElementById('annualBtn').className = 'px-5 py-2 rounded-full ' + (isAnnual ? 'bg-primary text-white' : 'text-on-surface') + ' text-sm font-semibold transition-all';
  document.querySelectorAll('.price-display').forEach(function (el) {
    el.textContent = '$' + (isAnnual ? el.dataset.annual : el.dataset.monthly);
  });
  document.querySelectorAll('.annual-note').forEach(function (el) { el.classList.toggle('hidden', !isAnnual); });
  document.querySelectorAll('.period-label').forEach(function (el) {
    el.textContent = isAnnual ? '/mo billed annually' : '/mo';
  });
}

function markCurrentPlan() {
  document.querySelectorAll('[data-plan]').forEach(function (btn) {
    var isCurrent = btn.dataset.plan === currentPlanSlug;
    if (!btn.dataset.label) btn.dataset.label = btn.textContent.trim();
    btn.disabled = isCurrent;
    btn.classList.toggle('opacity-60', isCurrent);
    btn.textContent = isCurrent ? careT('plans.current', null, 'Your current plan') : btn.dataset.label;
  });
}

async function selectPlan(slug) {
  var result = await choosePlan(slug);
  if (!result.ok) return showToast(apiErrorText(result), 'error');
  var name = result.data.plan.name;
  currentPlanSlug = result.data.plan.slug;
  markCurrentPlan();
  document.getElementById('planModalTitle').textContent = careT('plans.selectedTitle', { name: name }, name + ' plan selected');
  document.getElementById('planModalSub').textContent = careT('plans.selectedBody', null, 'Saved to your account. This is a demo: no payment was taken.');
  document.getElementById('planModal').classList.remove('hidden');
}

document.addEventListener('DOMContentLoaded', async function () {
  var session = await requireAuth();
  if (!session) return;
  var result = await getCurrentPlan();
  currentPlanSlug = result.ok && result.data ? result.data.slug : null;
  markCurrentPlan();
  window.addEventListener('careconnect:redraw-dynamic', markCurrentPlan);
});
