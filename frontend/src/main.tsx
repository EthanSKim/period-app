import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { authService } from './api.ts'

// ── Service Worker message handler ───────────────────────────────────────────
//
// The service worker cannot access localStorage (where the auth token lives),
// so when it detects a push subscription rotation (pushsubscriptionchange event)
// it posts a message here. The app shell then re-registers the new subscription
// with the backend using the stored auth token.

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const buffer = new ArrayBuffer(rawData.length)
  const output = new Uint8Array(buffer)
  for (let i = 0; i < rawData.length; ++i) {
    output[i] = rawData.charCodeAt(i)
  }
  return output
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('message', async (event) => {
    if (event.data?.type === 'PUSH_SUBSCRIPTION_CHANGED') {
      // Only act if the user is still authenticated
      if (!authService.isAuthenticated()) return

      try {
        // Re-subscribe with a fresh browser subscription
        const reg = await navigator.serviceWorker.ready
        const keyData = await authService.getVapidPublicKey()
        const newSub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(keyData.public_key),
        })
        const subJSON = newSub.toJSON()
        await authService.subscribePush({
          endpoint: subJSON.endpoint,
          keys: { p256dh: subJSON.keys?.p256dh, auth: subJSON.keys?.auth },
        })
        console.log('[App] Push subscription rotated and re-registered successfully.')
      } catch (err) {
        console.error('[App] Failed to re-register rotated push subscription:', err)
      }
    }
  })
}

// ── React root ───────────────────────────────────────────────────────────────

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
