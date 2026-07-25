/*
  Period Tracker — Service Worker
  Version: 2.0.1
  Handles: PWA install, Web Push events, notification clicks, subscription rotation.

  VERSIONING NOTE: Bump the version comment above to ensure browsers detect
  an updated service worker and re-register within one update cycle.
  updateViaCache: 'none' is set in index.html so updates reach users promptly.
*/

// ── Install & Activate ────────────────────────────────────────────────────────

self.addEventListener('install', (event) => {
  // Activate immediately — don't wait for old tabs to close
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Claim all open clients so this SW controls them right away
  event.waitUntil(self.clients.claim());
});

// ── Fetch (pass-through, keep PWA installable) ────────────────────────────────

self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request).catch((err) => {
      console.warn('[SW] Fetch failed for:', event.request.url, err);
    })
  );
});

// ── Push Event Handler ────────────────────────────────────────────────────────

self.addEventListener('push', (event) => {
  // Fallback shown if payload is missing or malformed — a visible notification
  // is always better than a silent failure.
  const FALLBACK_TITLE = 'period.';
  const FALLBACK_BODY = 'Check your cycle update';
  const FALLBACK_ICON = '/icon-192.png';
  const FALLBACK_URL = '/';

  let title = FALLBACK_TITLE;
  let body = FALLBACK_BODY;
  let icon = FALLBACK_ICON;
  let url = FALLBACK_URL;

  if (event.data) {
    try {
      const payload = event.data.json();
      title = payload.title || FALLBACK_TITLE;
      body = payload.body || FALLBACK_BODY;
      icon = payload.icon || FALLBACK_ICON;
      url = payload.url || FALLBACK_URL;
    } catch (err) {
      // Malformed JSON — use fallback values already set above
      console.warn('[SW] Failed to parse push payload, using fallback:', err);
    }
  }

  const options = {
    body,
    icon,
    badge: '/icon-192.png',
    // Persist the notification until the user interacts with it
    requireInteraction: false,
    // Tag groups notifications so a new one replaces the old one of the same type
    tag: title,
    // Store the target URL in notification data for the click handler
    data: { url },
    // Vibration pattern for Android (short-pause-short)
    vibrate: [150, 50, 150],
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// ── Notification Click Handler ────────────────────────────────────────────────

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  // Determine the target URL: payload URL or app root
  const targetUrl = (event.notification.data && event.notification.data.url)
    ? event.notification.data.url
    : '/';

  event.waitUntil(
    // Check if the app is already open in a window
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // If a window is already open, navigate it to the target URL and focus it
      for (const client of clientList) {
        if ('navigate' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      // Otherwise open a new window
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })
  );
});

// ── Push Subscription Change Handler ─────────────────────────────────────────
//
// Browsers can silently rotate push subscriptions (e.g. when the push service
// invalidates an old endpoint). If we don't re-register the new subscription
// the backend will keep trying the old endpoint and all pushes will silently fail.
//
// This handler catches the rotation event, fetches the VAPID public key from the
// backend, creates a fresh subscription, and POSTs it to keep the backend in sync.

self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(
    (async () => {
      try {
        // Fetch the VAPID public key from the backend
        const response = await fetch('/push/vapid-public-key');
        if (!response.ok) {
          throw new Error(`Failed to fetch VAPID key: ${response.status}`);
        }
        const { public_key: vapidPublicKey } = await response.json();

        // Convert VAPID key from URL-safe base64 to Uint8Array
        const padding = '='.repeat((4 - (vapidPublicKey.length % 4)) % 4);
        const base64 = (vapidPublicKey + padding)
          .replace(/-/g, '+')
          .replace(/_/g, '/');
        const rawData = atob(base64);
        const applicationServerKey = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
          applicationServerKey[i] = rawData.charCodeAt(i);
        }

        // Subscribe with the new key
        const newSubscription = await self.registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey,
        });

        // Retrieve the auth token from the first controlled client's storage
        // We broadcast a message to the app to handle re-registration, since the
        // SW cannot access localStorage directly.
        const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
        if (clients.length > 0) {
          // Ask the app shell to re-register the subscription (it has the auth token)
          clients[0].postMessage({
            type: 'PUSH_SUBSCRIPTION_CHANGED',
            subscription: newSubscription.toJSON(),
          });
          console.log('[SW] pushsubscriptionchange: notified app shell to re-register.');
        } else {
          // No open clients — log the event; the app will sync on next open via
          // the syncPushSubscription() call in NotificationPrompt on load.
          console.warn('[SW] pushsubscriptionchange: no open clients to notify.');
        }
      } catch (err) {
        console.error('[SW] Failed to handle pushsubscriptionchange:', err);
      }
    })()
  );
});
