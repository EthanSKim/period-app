import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authService } from '../api'

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/')
  const rawData = window.atob(base64)
  const buffer = new ArrayBuffer(rawData.length)
  const output = new Uint8Array(buffer)
  for (let i = 0; i < rawData.length; ++i) {
    output[i] = rawData.charCodeAt(i)
  }
  return output
}

type NotificationState = 'enabled' | 'disabled' | 'blocked' | 'unsupported'

interface NotificationTypeItem {
  id: string
  icon: string
  title: string
  description: string
}

const NOTIFICATION_TYPES: NotificationTypeItem[] = [
  {
    id: 'luteal_phase_heads_up',
    icon: '🧠',
    title: '8 days before your period — luteal phase heads-up',
    description: 'The week before your period can bring mood changes, fatigue, and physical symptoms. This reminder helps you prepare.',
  },
  {
    id: 'period_3_days',
    icon: '🔔',
    title: '3 days before your period',
    description: 'Expected cycle starting in 3 days.',
  },
  {
    id: 'period_1_day',
    icon: '🔔',
    title: '1 day before your period',
    description: 'Expected cycle starting tomorrow.',
  },
  {
    id: 'fertile_1_day',
    icon: '🥚',
    title: '1 day before your fertile window',
    description: 'Fertile window starting tomorrow.',
  },
]

export const NotificationSettings: React.FC = () => {
  const navigate = useNavigate()
  const [notifState, setNotifState] = useState<NotificationState>('disabled')
  const [isLoading, setIsLoading] = useState(true)
  const [toggleLoading, setToggleLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isIOSDevice, setIsIOSDevice] = useState(false)
  const [isStandaloneMode, setIsStandaloneMode] = useState(true)

  const checkState = async () => {
    setIsLoading(true)
    setErrorMessage(null)

    // Check iOS and standalone mode
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as any).MSStream
    setIsIOSDevice(isIOS)

    const isStandalone =
      (window.navigator as any).standalone === true ||
      window.matchMedia('(display-mode: standalone)').matches
    setIsStandaloneMode(isStandalone)

    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
      setNotifState('unsupported')
      setIsLoading(false)
      return
    }

    const permission = Notification.permission

    if (permission === 'denied') {
      setNotifState('blocked')
      setIsLoading(false)
      return
    }

    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()

      if (permission === 'granted' && sub) {
        setNotifState('enabled')
      } else {
        setNotifState('disabled')
      }
    } catch (err: any) {
      console.error('Error checking SW subscription:', err)
      setNotifState('disabled')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!authService.isAuthenticated()) {
      navigate('/login')
      return
    }
    checkState()
  }, [navigate])

  const handleToggle = async () => {
    if (toggleLoading) return
    setToggleLoading(true)
    setErrorMessage(null)

    try {
      const reg = await navigator.serviceWorker.ready

      if (notifState === 'enabled') {
        // Turning OFF: unsubscribe
        const sub = await reg.pushManager.getSubscription()
        if (sub) {
          try {
            await authService.unsubscribePush(sub.endpoint)
          } catch (err: any) {
            if (err.message !== 'Subscription not found for this user') {
              throw err
            }
          }
          await sub.unsubscribe()
        }
        localStorage.setItem('notifications_disabled_by_user', 'true')
        setNotifState('disabled')
      } else {
        // Turning ON: request permission or subscribe directly
        const permission = Notification.permission

        if (permission === 'denied') {
          setNotifState('blocked')
          setToggleLoading(false)
          return
        }

        let finalPermission: NotificationPermission = permission
        if (permission === 'default') {
          finalPermission = await Notification.requestPermission()
        }

        if (finalPermission === 'granted') {
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
          setNotifState('enabled')
        } else if (finalPermission === 'denied') {
          setNotifState('blocked')
        } else {
          setNotifState('disabled')
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update notification settings.')
    } finally {
      setToggleLoading(false)
    }
  }

  const getStatusBadge = () => {
    switch (notifState) {
      case 'enabled':
        return (
          <div className="status-badge-container">
            <span className="status-indicator status-on"></span>
            <span className="status-text">Notifications are on</span>
          </div>
        )
      case 'disabled':
        return (
          <div className="status-badge-container">
            <span className="status-indicator status-off"></span>
            <span className="status-text">Notifications are off</span>
          </div>
        )
      case 'blocked':
        return (
          <div className="status-badge-container">
            <span className="status-indicator status-blocked"></span>
            <span className="status-text">Blocked by browser</span>
          </div>
        )
      case 'unsupported':
      default:
        return (
          <div className="status-badge-container">
            <span className="status-indicator status-off"></span>
            <span className="status-text">Not supported</span>
          </div>
        )
    }
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="logo-group" onClick={() => navigate('/home')} style={{ cursor: 'pointer' }}>
          <span className="logo-emoji">🌸</span>
          <span className="logo-text">period.</span>
        </div>
        <button onClick={() => navigate('/home')} className="btn btn-secondary">
          Back
        </button>
      </header>

      <main className="dashboard-main">
        <div className="welcome-card dashboard-summary-card">
          <h1 className="dashboard-greeting" style={{ fontSize: '24px', marginBottom: '8px' }}>
            Notification Settings
          </h1>
          <p className="subtitle" style={{ marginBottom: '24px' }}>
            Control how and when you get cycle reminders
          </p>

          {errorMessage && (
            <div className="auth-error-banner" role="alert" style={{ marginBottom: '16px' }}>
              <span className="error-icon">⚠️</span>
              <span>{errorMessage}</span>
            </div>
          )}

          {isLoading ? (
            <div className="dashboard-loading" style={{ minHeight: '120px' }}>
              <div className="spinner"></div>
              <p>Checking status...</p>
            </div>
          ) : (
            <div className="settings-panel">
              {/* Status Row */}
              <div className="settings-row" style={{ marginBottom: '24px' }}>
                <span className="settings-row-label">Current Status</span>
                {getStatusBadge()}
              </div>

              {/* Action / Toggle block */}
              <div className="settings-control-box">
                {isIOSDevice && !isStandaloneMode ? (
                  <div className="pwa-install-instructions">
                    <span className="instructions-icon">📱</span>
                    <p>
                      <strong>Installation Required:</strong> Push notifications are only
                      supported on iOS when installed as a PWA. Tap the Safari share button
                      and select <strong>"Add to Home Screen"</strong> to install it.
                    </p>
                  </div>
                ) : notifState === 'unsupported' ? (
                  <div className="pwa-install-instructions">
                    <span className="instructions-icon">⚠️</span>
                    <p>
                      Push notifications are not supported on this device or web browser.
                      Please use a modern browser like Google Chrome or Safari.
                    </p>
                  </div>
                ) : notifState === 'blocked' ? (
                  <div className="blocked-instructions">
                    <span className="instructions-icon">🔒</span>
                    <p>
                      <strong>Notifications Blocked:</strong> You have blocked notifications
                      for this website. Please open your browser settings or site permissions
                      dialog to allow notifications, then reload this page.
                    </p>
                  </div>
                ) : (
                  <div className="toggle-container">
                    <div className="toggle-label-group">
                      <span className="toggle-title">Allow Alerts</span>
                      <span className="toggle-subtitle">
                        Send reminders before my period and fertile window
                      </span>
                    </div>
                    <label className="switch-toggle" htmlFor="notif-toggle-switch">
                      <input
                        id="notif-toggle-switch"
                        type="checkbox"
                        checked={notifState === 'enabled'}
                        onChange={handleToggle}
                        disabled={toggleLoading}
                        aria-label="Allow Alerts"
                      />
                      <span className="switch-slider"></span>
                    </label>
                  </div>
                )}
              </div>

              {/* Notification types description */}
              <div className="settings-details-section">
                <h3 className="section-title">📬 Reminders you will receive:</h3>
                <ul className="notif-features-list">
                  {NOTIFICATION_TYPES.map((type) => (
                    <li key={type.id}>
                      <span className="list-bullet">{type.icon}</span>
                      <div>
                        <strong>{type.title}</strong>
                        <p>{type.description}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
