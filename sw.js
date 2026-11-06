// Service worker de la visite 3D (GitHub Pages) : la page est servie « réseau d'abord » (les nouvelles versions arrivent),
// les ressources (scène, éclairage cuit, three.js sur cdn.jsdelivr.net) « cache d'abord » (hors-ligne après la première visite).
// Si une ressource change de contenu sans changer de nom : lui donner une nouvelle URL (AV dans la page → ?v=N), ne pas changer CACHE.
// Une nouvelle version du worker recopie ce que les anciens caches ocean3d-* contenaient : le hors-ligne survit aux mises à jour.
const CACHE = 'ocean3d-v1';
const PRE = ['./index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const cur = await caches.open(CACHE);
    for (const k of await caches.keys()) {
      if (k === CACHE || !k.startsWith('ocean3d-')) continue;   // other Pages apps share this origin: leave their caches alone
      const old = await caches.open(k);
      for (const req of await old.keys()) if (!/\/index\.html$/.test(req.url) && !(await cur.match(req))) await cur.put(req, await old.match(req));
      await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).then(r => {
      if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put('./index.html', copy)); }
      return r;
    }).catch(() => caches.match('./index.html')));
    return;
  }
  if (url.origin !== location.origin && url.hostname !== 'cdn.jsdelivr.net') return;   // polices Google, etc. : réseau normal
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
    if (r.ok) { const copy = r.clone(); e.waitUntil(caches.open(CACHE).then(c => c.put(req, copy))); }
    return r;
  })));
});
