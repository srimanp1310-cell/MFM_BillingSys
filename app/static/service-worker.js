/* App-shell cache + offline fallback + push notifications.
   Billing/stock actions always need the server; offline mode only keeps the
   shell loading gracefully. */

const CACHE = 'mfm-shell-v2';
const SHELL = [
  '/offline',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/icons/icon-192.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  if (req.mode === 'navigate') {
    // pages: network first, offline fallback
    event.respondWith(fetch(req).catch(() => caches.match('/offline')));
    return;
  }
  if (new URL(req.url).pathname.startsWith('/static/')) {
    // static assets: stale-while-revalidate — serve cached copy instantly,
    // refresh it in the background so replaced files (e.g. logo) update
    event.respondWith(
      caches.match(req).then((hit) => {
        const refresh = fetch(req).then((resp) => {
          if (resp.ok) {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        }).catch(() => hit);
        return hit || refresh;
      })
    );
  }
});

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data.json(); } catch (e) { /* ignore */ }
  const title = data.title || 'MFM Billing';
  event.waitUntil(self.registration.showNotification(title, {
    body: data.body || '',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    data: { url: data.url || '/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data && event.notification.data.url ? event.notification.data.url : '/';
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
    for (const w of wins) {
      if ('focus' in w) { w.navigate(url); return w.focus(); }
    }
    return clients.openWindow(url);
  }));
});
