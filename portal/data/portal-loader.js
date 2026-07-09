/**
 * ════════════════════════════════════════════════════════════════════
 *  PORTAL SHARED LOADER — included by every portal page
 * ════════════════════════════════════════════════════════════════════
 *  Loads portal-config.json, provides shared data fetching, and manages
 *  the API key across all pages. Every page calls PORTAL.init() on load.
 *
 *  If the config is unreachable (offline, file:// mode, testing), all
 *  methods degrade gracefully — pages fall back to their standalone behavior.
 *
 *  Usage in any portal page:
 *    <script src="../data/portal-loader.js"></script>
 *    <script>
 *      PORTAL.init().then(function() {
 *        // Config loaded — use PORTAL.config, PORTAL.loadData('equity'), etc.
 *      });
 *    </script>
 * ════════════════════════════════════════════════════════════════════
 */
var PORTAL = (function() {

  var config = null;
  var dataRoot = '../data/';
  var ready = false;

  // ── Init: load config, restore API key ──
  function init() {
    return loadConfig().then(function(cfg) {
      if (cfg) {
        config = cfg;
        dataRoot = cfg.dataRoot || '../data/';
        ready = true;
        // Shared API key: config → localStorage → null
        if (cfg.apiKey) {
          window._AK = cfg.apiKey;
        } else {
          var stored = null;
          try { stored = localStorage.getItem('mhc_portal_apikey'); } catch(e) {}
          if (stored) window._AK = stored;
        }
      }
      return cfg;
    });
  }

  // ── Load the config file ──
  function loadConfig() {
    return fetch(dataRoot + 'portal-config.json', { credentials: 'include' })
      .then(function(r) { return r.ok ? r.json() : null; })
      .catch(function() {
        console.log('[portal] Config not available — standalone mode');
        return null;
      });
  }

  // ── Load a data source by key (e.g. 'equity', 'research', 'ideas') ──
  function loadData(sourceKey) {
    if (!config || !config.dataSources || !config.dataSources[sourceKey]) {
      return Promise.resolve(null);
    }
    var src = config.dataSources[sourceKey];
    if (!src.file) return Promise.resolve(null);
    return fetch(dataRoot + src.file, { credentials: 'include' })
      .then(function(r) { return r.ok ? r.json() : null; })
      .catch(function(e) {
        console.log('[portal] Could not load ' + sourceKey + ':', e.message);
        return null;
      });
  }

  // ── Get strategy content (narrative, IC message) ──
  function getStrategy() {
    return config && config.strategy ? config.strategy : null;
  }

  // ── Get nav items ──
  function getNav() {
    return config && config.nav ? config.nav : [];
  }

  // ── Save API key (shared across pages via localStorage) ──
  function saveApiKey(key) {
    window._AK = key;
    try { localStorage.setItem('mhc_portal_apikey', key); } catch(e) {}
  }

  // ── Get API key ──
  function getApiKey() {
    return window._AK || null;
  }

  // ── Clear API key ──
  function clearApiKey() {
    window._AK = null;
    try { localStorage.removeItem('mhc_portal_apikey'); } catch(e) {}
  }

  // ── Last update timestamp for a data source ──
  function getLastUpdate(sourceKey) {
    if (!config || !config.dataSources || !config.dataSources[sourceKey]) return null;
    return config.dataSources[sourceKey].updated;
  }

  // ── Public API ──
  return {
    init: init,
    loadData: loadData,
    getStrategy: getStrategy,
    getNav: getNav,
    saveApiKey: saveApiKey,
    getApiKey: getApiKey,
    clearApiKey: clearApiKey,
    getLastUpdate: getLastUpdate,
    get config() { return config; },
    get ready() { return ready; },
    get dataRoot() { return dataRoot; }
  };

})();
