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
