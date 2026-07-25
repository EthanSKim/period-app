import React, { useEffect, useState } from 'react'
import { authService } from '../api'

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/')
  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}

interface NotificationPromptProps {
  onSubscriptionStatusChange?: (isSubscribed: boolean) => void
  forceOpen?: boolean
  onRequestClose?: () => void
}

export const NotificationPrompt: React.FC<NotificationPromptProps> = ({
  onSubscriptionStatusChange,
  forceOpen = false,
  onRequestClose,
}) => {
  const [showPrompt, setShowPrompt] = useState(false)
  const [deniedMessage, setDeniedMessage] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isIOSDevice, setIsIOSDevice] = useState(false)
  const [isStandaloneMode, setIsStandaloneMode] = useState(true)

  useEffect(() => {
    if (forceOpen) {
      setShowPrompt(true)
      if (Notification.permission === 'denied') {
        setDeniedMessage(true)
      }
      return
    }

    const checkState = async () => {
      // Check iOS standalone mode
      const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as any).MSStream
      setIsIOSDevice(isIOS)

      const isStandalone =
        (window.navigator as any).standalone === true ||
        window.matchMedia('(display-mode: standalone)').matches
      setIsStandaloneMode(isStandalone)

      // Suppress prompt if not standalone on iOS
      if (isIOS && !isStandalone) {
        return
      }

      // Check browser permissions
      if (!('Notification' in window) || !('serviceWorker' in navigator)) {
        return
      }

      const permission = Notification.permission
      if (permission === 'denied' || permission === 'granted') {
        // If granted, sync subscription if missing, but don't prompt
        if (permission === 'granted' && localStorage.getItem('notifications_disabled_by_user') !== 'true') {
          syncPushSubscription()
        }
        return
      }

      // Check 7-day prompt dismissal cooldown
      const dismissedUntil = localStorage.getItem('push_prompt_dismissed_until')
      if (dismissedUntil && Date.now() < parseInt(dismissedUntil, 10)) {
        return
      }

      // Check if user has logged cycles
      try {
        const cycles = await authService.getCycles()
        if (cycles.length >= 1) {
          setShowPrompt(true)
        }
      } catch {
        // Auth or network failure, suppress prompt
      }
    }

    checkState()
  }, [forceOpen])

  const syncPushSubscription = async () => {
    try {
      const reg = await navigator.serviceWorker.ready
      const existingSub = await reg.pushManager.getSubscription()
      if (!existingSub) {
        const keyData = await authService.getVapidPublicKey()
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(keyData.public_key),
        })
        const subJSON = sub.toJSON()
        await authService.subscribePush({
          endpoint: subJSON.endpoint,
          keys: {
            p256dh: subJSON.keys?.p256dh,
            auth: subJSON.keys?.auth,
          },
        })
        localStorage.removeItem('notifications_disabled_by_user')
        if (onSubscriptionStatusChange) onSubscriptionStatusChange(true)
      }
    } catch (err) {
      console.error('Failed to sync push subscription:', err)
    }
  }

  const handleOptIn = async () => {
    setErrorMessage(null)
    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
      setErrorMessage('Push notifications are not supported on this browser.')
      return
    }

    try {
      const permission = Notification.permission
      if (permission === 'granted') {
        await syncPushSubscription()
        setShowPrompt(false)
        onRequestClose?.()
        return
      }

      const result = await Notification.requestPermission()
      if (result === 'granted') {
        await syncPushSubscription()
        setShowPrompt(false)
        onRequestClose?.()
      } else if (result === 'denied') {
        setDeniedMessage(true)
      } else {
        setShowPrompt(false)
        onRequestClose?.()
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to turn on notifications.')
    }
  }

  const handleClose = () => {
    setShowPrompt(false)
    onRequestClose?.()
  }

  const handleDismiss = () => {
    const dismissedUntil = Date.now() + 7 * 24 * 60 * 60 * 1000 // 7 days
    localStorage.setItem('push_prompt_dismissed_until', dismissedUntil.toString())
    setShowPrompt(false)
    onRequestClose?.()
  }

  // Render iOS Home Screen prompt banner if iOS and not running as PWA standalone
  // (only when auto-triggered, not when user opened settings manually)
  if (!forceOpen && isIOSDevice && !isStandaloneMode) {
    return (
      <div className="ios-pwa-banner">
        <span className="banner-emoji">📱</span>
        <span>
          <strong>Get period alerts:</strong> Tap the Safari Share button{' '}
          <span style={{ fontSize: '16px' }}>⎙</span> and select{' '}
          <strong>'Add to Home Screen'</strong> to enable notifications.
        </span>
      </div>
    )
  }

  if (!showPrompt) {
    return null
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <h3 className="modal-title">🔔 Stay Notified</h3>
        <p className="modal-subtitle">Get head-ups before your period starts</p>

        {errorMessage && (
          <div className="auth-error-banner" role="alert" style={{ marginBottom: '16px' }}>
            <span className="error-icon">⚠️</span>
            <span>{errorMessage}</span>
          </div>
        )}

        {deniedMessage ? (
          <div>
            <p className="prompt-text" style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
              Notifications are blocked in your browser settings. To receive reminders, please
              unblock notifications for this site in your browser's site preferences.
            </p>
            <div className="form-actions-row" style={{ marginTop: '20px' }}>
              <button
                type="button"
                onClick={handleClose}
                className="btn btn-primary flex-fill"
              >
                Got it
              </button>
            </div>
          </div>
        ) : (
          <div>
            <p className="prompt-text" style={{ fontSize: '15px', color: 'var(--text-main)', lineHeight: '1.5' }}>
              Get a heads-up before your period arrives. We'll send you a reminder 1–3 days
              before your next expected period. You can turn this off anytime.
            </p>
            <div className="form-actions-row" style={{ marginTop: '24px' }}>
              <button
                type="button"
                onClick={handleOptIn}
                className="btn btn-primary flex-fill"
              >
                Turn on notifications
              </button>
              <button
                type="button"
                onClick={handleDismiss}
                className="btn btn-secondary"
              >
                Not now
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
