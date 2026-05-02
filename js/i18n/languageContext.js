/**
 * Vanilla "context" façade for parity with React LanguageContext APIs.
 * React screens can migrate to hooks later; static HTML uses CarePrefs + CareI18n directly.
 */
(function (global) {
  global.LanguageContext = {
    getLocale: function () {
      return global.CarePrefs.getLanguage();
    },
    setLocale: function (locale) {
      return global.CarePrefs.setLanguage(locale);
    },
    subscribeLocale: function (fn) {
      var handler = function (ev) {
        fn(ev.detail && ev.detail.locale);
      };
      global.addEventListener("careconnect:locale", handler);
      return function unsubscribe() {
        global.removeEventListener("careconnect:locale", handler);
      };
    },
    getPreferenceSnapshot: function () {
      return {
        language: global.CarePrefs.getLanguage(),
        location: global.CarePrefs.getLocation(),
        preferredConsultLanguage: global.CarePrefs.getPreferredConsultLanguage(),
      };
    },
  };
})(typeof window !== "undefined" ? window : globalThis);
