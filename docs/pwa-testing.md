# PWA Testing & Verification Guide

This document describes how to test and verify the Progressive Web App (PWA) capabilities of the Period App, including installability and setup on Android, iOS, and local environments.

---

## 📱 Platform Testing Procedures

### 1. Google Chrome / Microsoft Edge (Android)
- **Local Dev Server / Tunneling**: Since PWA features require HTTPS (except for `localhost`), you can test locally by accessing `http://localhost:3000` or using a secure tunnel like **ngrok**:
  ```bash
  ngrok http 3000
  ```
- **Install Flow**:
  1. Open Chrome/Edge on Android and navigate to the secure HTTPS URL.
  2. A banner prompt "Add Period to Home screen" or a badge indicator should appear.
  3. Alternatively, open the three-dot menu and select **"Install App"** or **"Add to Home screen"**.
  4. Confirm the installation. The app will launch in standalone display mode (no browser address bar).

### 2. Apple Safari (iOS 16.4+)
- **Prerequisites**: Web Push and installation flows require a valid HTTPS configuration and iOS 16.4+.
- **Install Flow**:
  1. Open Safari on iOS and navigate to the HTTPS URL.
  2. Tap the **Share** button (upwards arrow icon).
  3. Scroll down and tap **"Add to Home Screen"**.
  4. Edit the name if desired and tap **Add**.
  5. Open the app from the home screen to verify it opens in `standalone` display mode with the custom pink flower rose icon.

### 3. Desktop Chrome / Edge
- **Verification**:
  1. Navigate to `http://localhost:3000`.
  2. Look for the "Install" icon (a computer icon with a down arrow) on the right side of the address bar.
  3. Click to install and verify it launches as a standalone app.

---

## 🔍 Audit & Verification Tools

### Lighthouse PWA Audit
To verify PWA compliance:
1. Open Chrome DevTools (`Cmd + Option + I`).
2. Go to the **Lighthouse** tab.
3. Select **PWA** under categories and check **Device: Mobile**.
4. Click **Analyze page load**.
5. Ensure the **"Installable"** check passes under the PWA results, which verifies:
   - Web App Manifest is loaded.
   - Service Worker is registered and intercepts fetch requests.
   - App has correct icon formats (192px and 512px).

### Browser DevTools
- Check **Application -> Manifest** to inspect name, theme colors, and icons.
- Check **Application -> Service Workers** to ensure `/sw.js` is registered, active, and running.

---

## 🔔 Push Notification Testing

### Testing the "App Open" Scenario (Desktop / Android Chrome)
1. Install the app and grant notification permission via the in-app prompt.
2. Use the debug endpoint to trigger a test push:
   ```bash
   curl -X POST http://localhost:8000/push/send-test \
     -H "Authorization: Bearer <your_jwt_token>"
   ```
3. A system notification should appear within a few seconds with the title, body, and the app icon.
4. Click the notification — the app should open and navigate to `/calendar`.

### Testing the "App Closed / Backgrounded" Scenario
> **Important:** This scenario cannot be fully tested in a desktop browser DevTools simulation.
> A real device with a valid push subscription (over HTTPS) is required.

1. Install the PWA on an Android device via Chrome.
2. Grant notification permission and ensure the subscription is registered (check via `GET /push/subscriptions`).
3. Close/background the app completely.
4. Trigger the scheduler job (or wait for 9 AM UTC), or use `POST /push/send-test`.
5. A notification should appear in the device notification tray.
6. Tapping it should open the app to `/calendar`.

### Testing on iOS Safari (16.4+)
1. Install the app to the home screen (see install flow above — HTTPS required).
2. Open the app **from the home screen icon** (must be in standalone mode).
3. The in-app notification prompt will appear after you've logged at least one cycle.
4. Grant permission — the push subscription will be registered with the backend.
5. Trigger a push via `POST /push/send-test` while the app is backgrounded.
6. A system notification should appear in the iOS notification center.

---

## 📋 Manual QA Checklist

### 1. PWA Installation
- [ ] **Android Installation**: Open the site in Chrome, tap "Install App" or "Add to Home Screen" in the menu. Confirm the app icon appears on the home screen.
- [ ] **iOS Installation**: Open the site in Safari, tap the Share icon, and select "Add to Home Screen". Confirm the app icon appears on the home screen.

### 2. Notification Opt-in & Permission Flow
- [ ] **No Onboarding Prompt**: Launch the PWA in standalone mode on a clean install. Verify no prompt displays before any cycles are logged.
- [ ] **Pre-prompt Display**: Log a cycle (minimum 1 start date). Verify the pre-prompt modal opens, explaining notification benefits, with options to "Turn on" or "Not now".
- [ ] **Not Now Dismissal (Cooldown)**: Tap "Not now". Confirm the modal closes. Reload the app; verify it does not re-prompt (cooldown state persisted in `localStorage` for 7 days).
- [ ] **Browser Dialog Trigger**: Open settings, click "Turn on" to force prompt. Click "Turn on notifications" on the modal. Confirm the native browser permission dialog triggers.
- [ ] **Subscription Registration**: Accept browser permissions. Verify `POST /push/subscribe` is called with endpoint/keys and returns `201 Created`.
- [ ] **Post-Denial Behavior**: If browser permission is denied, verify a non-guilt-tripping message explains how to re-enable it in browser settings and does not re-prompt.

### 3. Test Notification Delivery
- [ ] **Manual Push Dispatch**: Background the app. Dispatch a test notification payload:
  ```bash
  curl -X POST http://localhost:8000/push/send-test \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <TOKEN>" \
    -d '{"title":"Period Alert","body":"Expected in 1 day","url":"/calendar"}'
  ```
- [ ] **Device Reception**: Verify the system tray displays the notification with the custom flower icon, correct title, and body.

### 4. Tapping & Deep Link Navigation
- [ ] **Deep Linking**: Tap the notification while the app is backgrounded.
- [ ] **Target Focus**: Verify the app opens and immediately navigates to `/calendar` (or the specific url set in the payload).

### 5. Settings Screen Toggle & Unsubscribe
- [ ] **Turn Off Toggle**: In the home dashboard "Notifications" settings card, tap "Turn off".
- [ ] **Cleanup Request**: Verify that `DELETE /push/subscribe` is sent with the endpoint to remove the subscription, and `subscription.unsubscribe()` is called.
- [ ] **Dashboard Sync**: Confirm the card updates to show notifications are disabled.

---

## ⚠️ Known Platform Limitations

### iOS Low Power Mode — Silent Push Failure
**This is a known platform constraint, not a bug.**

On iOS, push notifications may **not display** if:
- The device is in **Low Power Mode**, AND
- The app has not been used recently (iOS aggressively limits background activity).

**Do not file this as a bug.** Advise users that Low Power Mode may suppress notifications. This is documented Apple behavior with no workaround available to web developers.

### iOS Push Requires Standalone Mode
Push notifications on iOS Safari **only work when the app is installed to the home screen and launched in standalone mode**. Opening the app as a regular browser tab will not receive push notifications on iOS. The app detects this and shows an install banner to guide users.

### Service Worker Update Propagation
Service worker updates are not instant. The registration uses `updateViaCache: 'none'` and calls `reg.update()` on every page load, so new SW versions (e.g. with updated push handlers) will be detected on the **next page load** after deployment, rather than requiring the user to wait up to 24 hours.

### Push Subscription Rotation
Browsers (especially Chrome on Android) can silently rotate push subscriptions without warning. The service worker handles the `pushsubscriptionchange` event and notifies the app shell via `postMessage` to re-register the new subscription with the backend. If the app was not open at rotation time, the subscription will be re-synced on next load via `syncPushSubscription()` in the notification prompt component.
