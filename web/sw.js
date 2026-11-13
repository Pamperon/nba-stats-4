const CACHE = 'nba-stats-4-shell-v73';
const ASSETS = ['/static/site-core.css','/static/site-app.js','/static/modules/team-links.js', '/static/team-links.css', '/static/modules/insights.js', '/static/insights.css', '/', '/static/style.css', '/static/app.js', '/static/features.js', '/static/hub-nav.js', '/static/modules/router.js', '/static/modules/sections.js', '/static/modules/assets.js', '/static/modules/design.js', '/static/design-system.css', '/static/modules/calendar-data.js', '/static/modules/match-charts.js', '/static/modules/match-data.js', '/static/icon.svg', '/static/icon-192.png', '/static/icon-512.png', '/static/icon-maskable-192.png', '/static/icon-maskable-512.png', '/static/favicon-32.png', '/static/favicon.ico', '/static/apple-touch-icon.png', '/static/manifest.webmanifest'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('nba-stats-4-shell-') && key !== CACHE)
      .map(key => caches.delete(key))
  )));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin ||
      (url.pathname.startsWith('/api/') || url.pathname.startsWith('/admin/'))) return;
  event.respondWith(fetch(event.request).catch(async () => {
    const cached = await caches.match(event.request, {ignoreSearch: true});
    return cached || (event.request.mode==='navigate' ? await caches.match('/') : null) || Response.error();
  }));
});
