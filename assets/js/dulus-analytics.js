(function (global) {
  'use strict';

  /* ==========================================================================
     DULUS ANALYTICS SDK v2 — canonical event, multi-provider fan-out
     ==========================================================================
     Proveedores soportados: Amplitude, Mixpanel, PostHog, Datadog RUM, Sentry.
     No envía secrets, prompts ni payloads de cliente.
     Si un provider no está configurado (key vacía), se ignora de forma silenciosa.
  */

  // Configuración por site. Sobreescribir con window.DULUS_ANALYTICS_CONFIG antes del init.
  const DEFAULTS = {
    site: location.hostname.includes('work') ? 'dulus.work' : 'dulus.ai',
    amplitudeKey: '',
    mixpanelToken: '',
    posthogKey: '',
    posthogHost: 'https://us.i.posthog.com',
    datadogRumAppId: '',
    datadogRumClientToken: '',
    datadogRumSite: 'datadoghq.com',
    datadogRumService: 'dulus-web',
    sentryDsn: '',
    sentryEnvironment: 'production',
    logLevel: 'warn',
    debug: false
  };

  const cfg = Object.assign({}, DEFAULTS, global.DULUS_ANALYTICS_CONFIG || {});
  const logger = {
    debug: (...a) => cfg.debug && console.log('[DulusAnalytics]', ...a),
    warn: (...a) => console.warn('[DulusAnalytics]', ...a),
    error: (...a) => console.error('[DulusAnalytics]', ...a)
  };

  // Sanitización básica: nunca mandes contenido de inputs libres, secrets ni URLs largas.
  function sanitize(obj) {
    const out = {};
    for (const [k, v] of Object.entries(obj || {})) {
      const key = String(k).toLowerCase();
      if (/pass|secret|token|key|dsn|credential|private|pwd|ssn/.test(key)) continue;
      if (typeof v === 'string' && v.length > 500) out[k] = v.slice(0, 500) + '…';
      else out[k] = v;
    }
    return out;
  }

  // Propiedades comunes de contexto para todos los eventos.
  function pageProps(extra) {
    const safe = sanitize(extra || {});
    return Object.assign({
      site: cfg.site,
      page: location.pathname || '/',
      host: location.hostname,
      url: location.href.split('?')[0].slice(0, 200),
      referrer: document.referrer ? document.referrer.split('?')[0].slice(0, 200) : undefined,
      viewport_width: window.innerWidth,
      viewport_height: window.innerHeight,
      language: navigator.language || 'unknown'
    }, safe);
  }

  // Inicialización de proveedores (lazy).
  let inited = false;
  function init() {
    if (inited) return;
    inited = true;

    // --- Amplitude ---
    if (cfg.amplitudeKey && global.amplitude && typeof global.amplitude.init === 'function') {
      try {
        global.amplitude.init(cfg.amplitudeKey, {
          defaultTracking: { pageViews: true, sessions: true, formInteractions: false, fileDownloads: false }
        });
        logger.debug('Amplitude init', cfg.amplitudeKey.slice(0, 8) + '...');
      } catch (e) { logger.warn('Amplitude init failed', e.message); }
    }

    // --- Mixpanel ---
    if (cfg.mixpanelToken && global.mixpanel && typeof global.mixpanel.init === 'function') {
      try {
        global.mixpanel.init(cfg.mixpanelToken, {
          track_pageview: true,
          persistence: 'localStorage',
          ignore_dnt: false
        });
        global.mixpanel.register({ site: cfg.site });
        logger.debug('Mixpanel init', cfg.mixpanelToken.slice(0, 8) + '...');
      } catch (e) { logger.warn('Mixpanel init failed', e.message); }
    }

    // --- PostHog ---
    if (cfg.posthogKey && global.posthog) {
      try {
        global.posthog.init(cfg.posthogKey, {
          api_host: cfg.posthogHost,
          loaded: (posthog) => { posthog.capture('page_loaded'); }
        });
        logger.debug('PostHog init', cfg.posthogKey.slice(0, 8) + '...');
      } catch (e) { logger.warn('PostHog init failed', e.message); }
    }

    // --- Datadog RUM ---
    if (cfg.datadogRumAppId && cfg.datadogRumClientToken && global.DD_RUM) {
      try {
        global.DD_RUM.init({
          applicationId: cfg.datadogRumAppId,
          clientToken: cfg.datadogRumClientToken,
          site: cfg.datadogRumSite,
          service: cfg.datadogRumService,
          env: cfg.sentryEnvironment,
          sessionSampleRate: 100,
          sessionReplaySampleRate: 20,
          trackUserInteractions: true,
          trackResources: true,
          trackLongTasks: true,
          defaultPrivacyLevel: 'mask-user-input'
        });
        global.DD_RUM.startSessionReplayRecording();
        logger.debug('Datadog RUM init');
      } catch (e) { logger.warn('Datadog RUM init failed', e.message); }
    }

    // --- Sentry ---
    if (cfg.sentryDsn && global.Sentry && global.Sentry.init) {
      try {
        global.Sentry.init({
          dsn: cfg.sentryDsn,
          environment: cfg.sentryEnvironment,
          tracesSampleRate: 0.2,
          replaysSessionSampleRate: 0.0,
          beforeSend(event) {
            // No mandar posibles secrets ni PII en el request de error
            if (event.request && event.request.url) event.request.url = event.request.url.split('?')[0];
            return event;
          }
        });
        logger.debug('Sentry init');
      } catch (e) { logger.warn('Sentry init failed', e.message); }
    }

    // Track automático: page loaded + clicks + scroll depth + heartbeat controlado
    try { track('page_loaded'); } catch (e) {}
    bindAutoTracking();
  }

  // Track canonical: fan-out a todos los providers activos.
  function track(eventName, properties) {
    const props = pageProps(properties);
    logger.debug('track', eventName, props);

    try {
      if (global.amplitude && typeof global.amplitude.track === 'function') {
        global.amplitude.track(eventName, props);
      }
    } catch (e) {}

    try {
      if (global.mixpanel && typeof global.mixpanel.track === 'function') {
        global.mixpanel.track(eventName, props);
      }
    } catch (e) {}

    try {
      if (global.posthog && typeof global.posthog.capture === 'function') {
        global.posthog.capture(eventName, props);
      }
    } catch (e) {}

    try {
      if (global.DD_RUM && typeof global.DD_RUM.addAction === 'function') {
        global.DD_RUM.addAction(eventName, props);
      }
    } catch (e) {}
  }

  // Identificación del usuario (solo con id no sensible, nunca email crudo si no es necesario).
  function identify(userId, traits) {
    const safeTraits = sanitize(traits || {});
    logger.debug('identify', userId, safeTraits);

    try { if (global.amplitude && global.amplitude.setUserId) { global.amplitude.setUserId(userId); global.amplitude.setUserProperties(safeTraits); } } catch (e) {}
    try { if (global.mixpanel && global.mixpanel.identify) { global.mixpanel.identify(userId); global.mixpanel.people.set(safeTraits); } } catch (e) {}
    try { if (global.posthog && global.posthog.identify) { global.posthog.identify(userId, safeTraits); } } catch (e) {}
  }

  function bindAutoTracking() {
    // Clicks en botones y enlaces
    document.addEventListener('click', function (e) {
      const el = e.target.closest('a, button, [role="button"], [data-track]');
      if (!el) return;
      const href = el.href || el.dataset.href || '';
      const label = (el.dataset.trackLabel || el.textContent || el.value || 'unknown').trim().slice(0, 60);
      track('click', {
        element: el.tagName.toLowerCase(),
        label: label,
        href: href.split('?')[0].slice(0, 200),
        data_track: el.dataset.track || undefined
      });
    }, true);

    // Scroll depth: 25, 50, 75, 100%
    const marks = {};
    window.addEventListener('scroll', throttle(function () {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      const pct = h > 0 ? Math.round((window.scrollY / h) * 100) : 0;
      [25, 50, 75, 100].forEach(function (m) {
        if (pct >= m && !marks[m]) {
          marks[m] = true;
          track('scroll_depth', { depth: m });
        }
      });
    }, 500));

    // Heartbeat ligero: 1 evento cada 30s, máximo 10 por página
    let beats = 0;
    const hb = setInterval(function () {
      beats += 1;
      track('heartbeat', { seconds: beats * 30 });
      if (beats >= 10) clearInterval(hb);
    }, 30000);
  }

  function throttle(fn, ms) {
    let last = 0, timer = null;
    return function (...args) {
      const now = Date.now();
      if (now - last >= ms) { last = now; fn.apply(this, args); }
      else if (!timer) { timer = setTimeout(() => { last = Date.now(); timer = null; fn.apply(this, args); }, ms - (now - last)); }
    };
  }

  // Expose API global
  global.dulusAnalytics = { init, track, identify, config: cfg };

  // Auto-inicializar si el usuario ya definió keys en window.DULUS_ANALYTICS_CONFIG
  // o si hay un script con data-config.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
