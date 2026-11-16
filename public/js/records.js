// The signed-in person's own records, read and written straight to Supabase.
//
// These are simple rows that belong to one user; row-level security
// (user_id = auth.uid()) is what protects them, so no backend hop is needed.
// Anything with rules across tables (appointments, orders, SOS) goes through
// the FastAPI backend instead — see js/api.js.
//
// Every function resolves to { ok, data, error }. Load after js/auth.js.
(function (global) {
  function fail(error) {
    console.warn('[records]', (error && error.message) || error);
    return { ok: false, data: null, error: (error && error.message) || 'failed' };
  }

  async function context() {
    var client = typeof getSupabase === 'function' ? getSupabase() : null;
    var user = typeof getUser === 'function' ? await getUser() : null;
    if (!client || !user) throw new Error('not signed in');
    return { client: client, user: user };
  }

  async function run(work) {
    try {
      var ctx = await context();
      return { ok: true, data: await work(ctx.client, ctx.user), error: null };
    } catch (err) {
      return fail(err);
    }
  }

  function unwrap(result) {
    if (result.error) throw result.error;
    return result.data;
  }

  function clean(text, max) {
    return String(text == null ? '' : text).trim().slice(0, max);
  }

  function numberOrNull(value) {
    if (value === '' || value == null) return null;
    var n = Number(value);
    return isFinite(n) ? n : null;
  }

  // Whole years between a YYYY-MM-DD date of birth and today; null if unknown.
  function ageFromDob(dob) {
    if (!dob) return null;
    var parts = String(dob).split('-').map(Number);
    if (parts.length !== 3 || parts.some(isNaN)) return null;
    var today = new Date();
    var age = today.getFullYear() - parts[0];
    if (today.getMonth() + 1 < parts[1] || (today.getMonth() + 1 === parts[1] && today.getDate() < parts[2])) age--;
    return age >= 0 && age <= 130 ? age : null;
  }

  var CareRecords = {
    ageFromDob: ageFromDob,

    // -> { displayName, email, medical: {date_of_birth, blood_type, phone, height_cm, weight_kg} | null,
    //      conditions: [{id, label}], allergies: [{id, label}] }
    getProfile: function () {
      return run(async function (db, user) {
        var results = await Promise.all([
          db.from('profiles').select('display_name').eq('id', user.id).maybeSingle(),
          db.from('medical_profiles').select('date_of_birth, blood_type, phone, height_cm, weight_kg').eq('user_id', user.id).maybeSingle(),
          db.from('profile_conditions').select('id, custom_label, condition_definitions(label)').eq('user_id', user.id).order('created_at'),
          db.from('profile_allergies').select('id, label').eq('user_id', user.id).order('created_at'),
        ]);
        var profile = unwrap(results[0]), medical = unwrap(results[1]);
        return {
          displayName: (profile && profile.display_name) || (user.user_metadata && user.user_metadata.full_name) || '',
          email: user.email || '',
          medical: medical || null,
          conditions: (unwrap(results[2]) || []).map(function (row) {
            return { id: row.id, label: row.custom_label || (row.condition_definitions && row.condition_definitions.label) || '' };
          }),
          allergies: unwrap(results[3]) || [],
        };
      });
    },

    // fields: { displayName, dateOfBirth, bloodType, phone, heightCm, weightKg }
    saveProfile: function (fields) {
      return run(async function (db, user) {
        var name = clean(fields.displayName, 80);
        if (name) {
          unwrap(await db.from('profiles').upsert({ id: user.id, display_name: name }, { onConflict: 'id' }));
          await db.auth.updateUser({ data: { full_name: name } });
        }
        unwrap(await db.from('medical_profiles').upsert({
          user_id: user.id,
          legal_full_name: name || null,
          date_of_birth: fields.dateOfBirth || null,
          blood_type: clean(fields.bloodType, 5) || null,
          phone: clean(fields.phone, 30) || null,
          height_cm: numberOrNull(fields.heightCm),
          weight_kg: numberOrNull(fields.weightKg),
        }, { onConflict: 'user_id' }));
        return true;
      });
    },

    addCondition: function (label) {
      return run(async function (db, user) {
        return unwrap(await db.from('profile_conditions').insert({ user_id: user.id, custom_label: clean(label, 80) }).select('id, custom_label').single());
      });
    },
    removeCondition: function (id) {
      return run(async function (db, user) {
        return unwrap(await db.from('profile_conditions').delete().eq('id', id).eq('user_id', user.id));
      });
    },

    addAllergy: function (label) {
      return run(async function (db, user) {
        return unwrap(await db.from('profile_allergies').insert({ user_id: user.id, label: clean(label, 80) }).select('id, label').single());
      });
    },
    removeAllergy: function (id) {
      return run(async function (db, user) {
        return unwrap(await db.from('profile_allergies').delete().eq('id', id).eq('user_id', user.id));
      });
    },

    listContacts: function () {
      return run(async function (db, user) {
        return unwrap(await db.from('emergency_contacts').select('id, name, phone, relationship').eq('user_id', user.id).order('created_at')) || [];
      });
    },
    addContact: function (contact) {
      return run(async function (db, user) {
        return unwrap(await db.from('emergency_contacts').insert({
          user_id: user.id,
          name: clean(contact.name, 80),
          phone: clean(contact.phone, 30),
          relationship: clean(contact.relationship, 40) || null,
        }).select('id, name, phone, relationship').single());
      });
    },
    removeContact: function (id) {
      return run(async function (db, user) {
        return unwrap(await db.from('emergency_contacts').delete().eq('id', id).eq('user_id', user.id));
      });
    },

    // -> [{ slug, name, price_cents_monthly, features }]
    listPlans: function () {
      return run(async function (db) {
        return unwrap(await db.from('plans').select('slug, name, price_cents_monthly, features').order('price_cents_monthly')) || [];
      });
    },

    // -> { slug, name, price_cents_monthly } | null
    currentPlan: function () {
      return run(async function (db, user) {
        var rows = unwrap(await db.from('subscriptions').select('status, plans(slug, name, price_cents_monthly)')
          .eq('user_id', user.id).eq('status', 'active').order('created_at', { ascending: false }).limit(1)) || [];
        return rows.length ? rows[0].plans : null;
      });
    },

    // Demo only: records the choice. No payment is taken and nothing is charged.
    choosePlan: function (slug) {
      return run(async function (db, user) {
        var plan = unwrap(await db.from('plans').select('id, slug, name, price_cents_monthly').eq('slug', slug).single());
        unwrap(await db.from('subscriptions').update({ status: 'cancelled' }).eq('user_id', user.id).eq('status', 'active'));
        unwrap(await db.from('subscriptions').insert({ user_id: user.id, plan_id: plan.id, status: 'active' }));
        return plan;
      });
    },
  };

  global.CareRecords = CareRecords;
})(typeof window !== 'undefined' ? window : globalThis);
