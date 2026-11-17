// CareConnect runtime config: where the API lives and which origin email links point to.
// Load before auth.js and api.js. window.CARE_API_BASE / window.CARE_WEB_ORIGIN override.
//   - native app (capacitor://localhost): hosted API and hosted web origin
//   - local dev (localhost / 127.0.0.1):  http://localhost:8000 and the page's own origin
//   - hosted web:                          hosted API and the page's own origin
(function (global) {
  var PROD_API_BASE = 'https://careconnect-api.onrender.com';
  var PROD_WEB_ORIGIN = 'https://careconnect-web.onrender.com';

  function resolveCareConfig(loc, overrides) {
    overrides = overrides || {};
    var isNativeApp = loc.protocol === 'capacitor:';
    var isLocalDev = !isNativeApp && (loc.hostname === 'localhost' || loc.hostname === '127.0.0.1');
    return {
      apiBase: overrides.apiBase || (isLocalDev ? 'http://localhost:8000' : PROD_API_BASE),
      webOrigin: overrides.webOrigin || (isNativeApp ? PROD_WEB_ORIGIN : loc.origin),
      isNativeApp: isNativeApp,
    };
  }

  var api = { resolveCareConfig: resolveCareConfig, PROD_API_BASE: PROD_API_BASE, PROD_WEB_ORIGIN: PROD_WEB_ORIGIN };
  if (global.location) {
    global.CARE_CONFIG = resolveCareConfig(global.location, {
      apiBase: global.CARE_API_BASE,
      webOrigin: global.CARE_WEB_ORIGIN,
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
