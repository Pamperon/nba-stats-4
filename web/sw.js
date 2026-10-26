const CACHE = 'nba-stats-4-shell-v4';
const ASSETS = ['/', '/static/style.css', '/static/app.js', '/static/icon.svg'];

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
      url.pathname.startsWith('/api/')) return;
  event.respondWith(fetch(event.request).catch(async () => {
    const cached = await caches.match(event.request, {ignoreSearch: true});
    return cached || Response.error();
  }));
});
