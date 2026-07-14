/*
  Simple pass-through PWA Service Worker for Period Tracker.
  Enables PWA installability requirements and acts as a foundation for Web Push Notifications.
*/

const CACHE_NAME = 'period-app-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request).catch((err) => {
      console.log('Fetch failed; returning network error.', err);
    })
  );
});
