/**
 * Preferences (localStorage) + CareI18n.t() + DOM [data-i18n] binding.
 */
(function init(global) {
  var STORAGE_LANG = "careconnect_language";
  var STORAGE_LOCATION = "careconnect_location";
  var STORAGE_CONSULT_LANG = "careconnect_preferred_consult_language";

  var DEFAULT_LOCATION = { country: "", city: "", postalCode: "" };

  function safeParse(raw, fallback) {
    try {
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  /** @type {CarePrefsGlobal} */
  var CarePrefs = {
    STORAGE_LANG: STORAGE_LANG,
    STORAGE_LOCATION: STORAGE_LOCATION,
    STORAGE_CONSULT_LANG: STORAGE_CONSULT_LANG,

    normalizeLocale: function (code) {
      var c = (code || "en").toLowerCase().split("-")[0];
      var allowed = global.CARE_LOCALES || ["en"];
      return allowed.indexOf(c) !== -1 ? c : "en";
    },

    getLanguage: function () {
      return CarePrefs.normalizeLocale(localStorage.getItem(STORAGE_LANG) || "en");
    },

    setLanguage: function (code, silent) {
      var lc = CarePrefs.normalizeLocale(code);
      localStorage.setItem(STORAGE_LANG, lc);
      global.dispatchEvent(new CustomEvent("careconnect:locale", { detail: { locale: lc } }));
      if (!silent && typeof CareI18n !== "undefined") CareI18n.apply(document);
      return lc;
    },

    getLocation: function () {
      var v = safeParse(localStorage.getItem(STORAGE_LOCATION), {});
      return {
        country: v.country || "",
        city: v.city || "",
        postalCode: v.postalCode || "",
      };
    },

    setLocation: function (loc) {
      var merged = Object.assign({}, DEFAULT_LOCATION, loc || {});
      localStorage.setItem(STORAGE_LOCATION, JSON.stringify(merged));
      global.dispatchEvent(new CustomEvent("careconnect:location", { detail: merged }));
      return merged;
    },

    /** Empty string = match any spoken language filter */
    getPreferredConsultLanguage: function () {
      return (
        localStorage.getItem(STORAGE_CONSULT_LANG) || ""
      ).trim();
    },

    setPreferredConsultLanguage: function (codeOrEmpty) {
      var val = codeOrEmpty == null ? "" : String(codeOrEmpty);
      localStorage.setItem(STORAGE_CONSULT_LANG, val);
      global.dispatchEvent(new CustomEvent("careconnect:consultlang", { detail: val }));
      return val;
    },

    /** For API payloads — excludes empty fields */
    getLocationForPayload: function () {
      var L = CarePrefs.getLocation();
      var out = {};
      if (L.country) out.country = L.country;
      if (L.city) out.city = L.city;
      if (L.postalCode) out.postalCode = L.postalCode;
      return Object.keys(out).length ? out : null;
    },
  };

  function dig(obj, parts) {
    var cur = obj;
    for (var i = 0; i < parts.length; i++) {
      if (cur == null) return null;
      cur = cur[parts[i]];
    }
    return cur;
  }

  /** Interface label for spoken language chips (English display names shared across locales) */
  var SPOKEN_LABELS = {
    en: "English",
    de: "German",
    tr: "Turkish",
    es: "Spanish",
    fr: "French",
    any: "",
  };

  /** @type {CareI18nGlobal} */
  var CareI18n = {
    t: function (key, vars, localeOpt) {
      var loc = localeOpt || CarePrefs.getLanguage();
      var parts = String(key || "").split(".");
      var table = global.CARE_TRANSLATIONS && global.CARE_TRANSLATIONS[loc];
      if (!table) table = global.CARE_TRANSLATIONS && global.CARE_TRANSLATIONS.en;
      var raw = dig(table, parts);
      if (typeof raw !== "string") return String(key || "");
      if (vars) {
        Object.keys(vars).forEach(function (k) {
          raw = raw.split("{{" + k + "}}").join(String(vars[k]));
        });
      }
      return raw;
    },

    spokenLanguageLabel: function (code) {
      return SPOKEN_LABELS[code] || code || "";
    },

    apply: function (rootEl) {
      rootEl = rootEl || document;

      rootEl.querySelectorAll("[data-i18n]").forEach(function (el) {
        var key = el.getAttribute("data-i18n");
        var count = el.getAttribute("data-i18n-count");
        var vars = count != null ? { count: count } : undefined;
        el.textContent = CareI18n.t(key, vars);
      });

      rootEl.querySelectorAll("[data-i18n-html]").forEach(function (el) {
        var key = el.getAttribute("data-i18n-html");
        el.innerHTML = CareI18n.t(key);
      });

      rootEl.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
        el.setAttribute("placeholder", CareI18n.t(el.getAttribute("data-i18n-placeholder")));
      });

      rootEl.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
        el.setAttribute("aria-label", CareI18n.t(el.getAttribute("data-i18n-aria")));
      });

      if (document.documentElement) document.documentElement.setAttribute("lang", CarePrefs.getLanguage());

      var titleKey = rootEl.body && rootEl.body.getAttribute("data-page-title-i18n");
      if (titleKey) document.title = CareI18n.t(titleKey);
    },

    bindProfileFormOnce: function () {
      var section = document.getElementById("carePreferencesSection");
      if (!section || section.dataset.bound === "1") return;
      section.dataset.bound = "1";

      var selLang = document.getElementById("carePrefLanguage");
      var selConsult = document.getElementById("carePrefConsultLanguage");
      var country = document.getElementById("carePrefCountry");
      var city = document.getElementById("carePrefCity");
      var postal = document.getElementById("carePrefPostal");
      var saveBtn = document.getElementById("carePrefSaveBtn");
      var status = document.getElementById("carePrefSaveStatus");

      if (selLang) {
        selLang.value = CarePrefs.getLanguage();
        selLang.addEventListener("change", function () {
          CarePrefs.setLanguage(selLang.value);
          CareI18n.apply(document);
        });
      }
      var L = CarePrefs.getLocation();
      if (country) country.value = L.country || "";
      if (city) city.value = L.city || "";
      if (postal) postal.value = L.postalCode || "";

      var cl = CarePrefs.getPreferredConsultLanguage();
      if (selConsult) selConsult.value = cl === "" ? "" : cl;

      if (saveBtn) {
        saveBtn.addEventListener("click", function () {
          CarePrefs.setLocation({
            country: country ? country.value.trim() : "",
            city: city ? city.value.trim() : "",
            postalCode: postal ? postal.value.trim() : "",
          });
          CarePrefs.setPreferredConsultLanguage(selConsult ? selConsult.value : "");
          if (status) {
            status.textContent = CareI18n.t("profile.saved");
            status.classList.remove("hidden");
            setTimeout(function () {
              status.classList.add("hidden");
            }, 2500);
          }
          CareI18n.apply(document);
        });
      }
    },

    bootstrap: function () {
      CarePrefs.getLanguage(); // ensure normalization
      CareI18n.apply(document);
      CareI18n.bindProfileFormOnce();
      CareI18n.bindHeaderLangSelectOnce("careHeaderLang");
      global.dispatchEvent(new CustomEvent("careconnect:redraw-dynamic"));
    },
  };

  /** Optional compact header language picker */
  CareI18n.bindHeaderLangSelectOnce = function (id) {
    var el = document.getElementById(id || "careHeaderLang");
    if (!el || el.dataset.bound === "1") return;
    el.dataset.bound = "1";
    el.value = CarePrefs.getLanguage();
    el.addEventListener("change", function () {
      CarePrefs.setLanguage(el.value);
      CareI18n.apply(document);
      global.dispatchEvent(new CustomEvent("careconnect:redraw-dynamic"));
    });
  };

  global.CarePrefs = CarePrefs;
  global.CareI18n = CareI18n;
})(typeof window !== "undefined" ? window : globalThis);

document.addEventListener("DOMContentLoaded", function () {
  if (typeof CareI18n !== "undefined") CareI18n.bootstrap();
});
