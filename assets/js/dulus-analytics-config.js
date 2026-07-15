/* DULUS.AI — loader del analytics SDK v2
   Copiar este archivo a: DEPLOY PRODUCTION DULUS AI FINAL/assets/js/dulus-analytics.js
   Inyectar en el <head> de cada HTML:
     <script async src="https://cdn.amplitude.com/libs/analytics-browser-2.11.1-min.js.gz"></script>
     <script src="assets/js/dulus-analytics.js"></script>
*/
(function () {
  window.DULUS_ANALYTICS_CONFIG = {
    site: 'dulus.ai',
    amplitudeKey: '2511c9e1fc597b8bc6b81f193cc615a2',
    mixpanelToken: '9c61bb3514113d743783ca9ee9922be0',
    posthogKey: 'REEMPLAZAR_CON_POSTHOG_KEY',   // <-- KevRojo: poner aquí
    datadogRumAppId: 'REEMPLAZAR_CON_DD_APP_ID',   // <-- KevRojo: poner aquí
    datadogRumClientToken: 'REEMPLAZAR_CON_DD_CLIENT_TOKEN', // <-- KevRojo: poner aquí
    sentryDsn: 'REEMPLAZAR_CON_SENTRY_DSN',        // <-- KevRojo: poner aquí
    debug: false
  };
})();
// El SDK unificado se carga después de este config.
