// Doctor records shared by consult.html and check.html.
// Loaded as a plain script (globals), after js/i18n/* and before the page script.

function labelsToLangCodes(labels) {
  if (!labels || !labels.length) return [];
  var nameMap = {
    english: 'en',
    german: 'de',
    turkish: 'tr',
    spanish: 'es',
    french: 'fr',
  };
  return labels.map(function (x) {
    var raw = String(x || '').trim();
    var low = raw.toLowerCase();
    var direct = nameMap[low];
    if (direct) return direct;
    var k = low.replace(/\./g, '');
    var kk;
    for (kk in nameMap) if (k.indexOf(kk) !== -1) return nameMap[kk];
    var two = raw.slice(0, 2).toLowerCase();
    if (['en', 'de', 'tr', 'es', 'fr'].indexOf(two) !== -1) return two;
    return '';
  }).filter(Boolean);
}

// Mirrors specialty_slug in backend/services/care_navigator.py
function slugFromSpecialtyName(name) {
  var s = String(name || '').toLowerCase();
  if (s.includes('emergency')) return 'emergency';
  if (s.includes('mental') || s.includes('psychiat') || s.includes('psycholog')) return 'mental_health';
  if (s.includes('cardio')) return 'cardiology';
  if (s.includes('derma')) return 'dermatology';
  if (s.includes('pediatr') || s.includes('paediatr')) return 'pediatrics';
  return 'general';
}

function normalizeDoctorRecord(d, fromApi) {
  var slug = slugFromSpecialtyName(d.specialty || d.specialization);
  var locStr = String(d.location || d.city_hint || '').trim();
  var city = d.city || locStr, country = d.country || '';
  var codes =
    Array.isArray(d.languageCodes) && d.languageCodes.length
      ? d.languageCodes
      : labelsToLangCodes(d.languages || []);
  if (!codes.length) codes = ['en'];
  return {
    id: d.id,
    name: d.name,
    specialty: d.specialty,
    specialtySlug: d.specialtySlug || slug,
    city: city,
    country: country,
    languages: d.languages,
    languageCodes: codes,
    img: d.img || d.image_url || null,
    rating: String(d.rating || '4.8'),
    is_available: typeof d.is_available === 'boolean' ? d.is_available : !!d.available,
    available:
      typeof d.available === 'boolean'
        ? d.available
        : typeof d.is_available === 'boolean'
          ? d.is_available
          : true,
    experience: d.experience || (d.years_experience ? d.years_experience + ' years' : ''),
  };
}

function doctorFromApi(d) {
  return normalizeDoctorRecord(
    {
      id: d.id,
      name: d.name,
      specialty: d.specialty,
      is_available: d.is_available,
      languages: d.languages,
      location: d.location,
      img: null,
      rating: '4.8',
    },
    true,
  );
}

// Photo when the record has one; otherwise initials. (A random stock face for a
// real provider is worse than no face.)
function doctorAvatarHTML(doc) {
  var escAttr = function (s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  };
  if (doc.img)
    return '<img src="' + escAttr(doc.img) + '" alt="" class="w-14 h-14 rounded-2xl object-cover shrink-0"/>';
  var initials = String(doc.name || '')
    .replace(/^(dr|prof)\.?\s+/i, '')
    .split(/\s+/)
    .map(function (w) { return w.charAt(0); })
    .join('')
    .slice(0, 2)
    .toUpperCase();
  return '<div aria-hidden="true" class="w-14 h-14 rounded-2xl shrink-0 bg-primary-fixed text-on-primary-fixed flex items-center justify-center font-bold">' +
    escAttr(initials) + '</div>';
}

// Demo data shown when the backend is unreachable.
const FALLBACK_DOCTORS = [
  normalizeDoctorRecord({ id: 1, name: 'Dr. Sarah Chen', specialty: 'Cardiology', experience: '12 years',
    rating: '4.9', available: true, img: 'https://i.pravatar.cc/80?img=47', city: 'Munich', country: 'Germany', languages: ['English', 'German'] }),
  normalizeDoctorRecord({ id: 2, name: 'Dr. Marcus Williams', specialty: 'Dermatology', experience: '8 years',
    rating: '4.8', available: true, img: 'https://i.pravatar.cc/80?img=25', city: 'Munich', country: 'Germany', languages: ['English', 'Spanish'] }),
  normalizeDoctorRecord({ id: 3, name: 'Dr. Priya Patel', specialty: 'Psychiatry', experience: '15 years',
    rating: '5.0', available: false, img: 'https://i.pravatar.cc/80?img=32', city: 'Berlin', country: 'Germany', languages: ['English', 'Hindi', 'German'] }),
  normalizeDoctorRecord({ id: 4, name: 'Dr. James Okafor', specialty: 'Pediatrics', experience: '10 years',
    rating: '4.7', available: true, img: 'https://i.pravatar.cc/80?img=48', city: 'Paris', country: 'France', languages: ['English', 'French'] }),
  normalizeDoctorRecord({ id: 5, name: 'Dr. Elena Gomez', specialty: 'General Practitioner', experience: '11 years',
    rating: '4.9', available: true, img: 'https://i.pravatar.cc/80?img=60', city: 'Madrid', country: 'Spain', languages: ['Spanish', 'English'] }),
  normalizeDoctorRecord({ id: 6, name: 'Dr. Aiden Park', specialty: 'Cardiology', experience: '7 years',
    rating: '4.6', available: false, img: 'https://i.pravatar.cc/80?img=15', city: 'Hamburg', country: 'Germany', languages: ['Korean', 'English', 'German'] }),
];
