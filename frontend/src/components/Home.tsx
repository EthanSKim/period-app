import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authService } from '../api'
import type { User, PredictionResponse } from '../api'
import { NotificationPrompt } from './NotificationPrompt'

const getTodayLocalDateString = (): string => {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const parseLocalDate = (dateStr: string): Date => {
  return new Date(dateStr + 'T00:00:00')
}

/** Derive notification status from browser permission + user-intent flag. */
function getNotifSubtitle(): string {
  if (!('Notification' in window) || !('serviceWorker' in navigator)) {
    return 'Not supported on this browser'
  }
  const perm = Notification.permission
  if (perm === 'denied') return 'Blocked in browser settings'
  if (perm === 'granted' && localStorage.getItem('notifications_disabled_by_user') !== 'true') {
    return 'Period & fertile window reminders are on'
  }
  return 'Tap Settings to enable reminders'
}

export const Home: React.FC = () => {
  const [user, setUser] = useState<User | null>(null)
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showNotifPrompt, setShowNotifPrompt] = useState(false)

  const navigate = useNavigate()
  const todayStr = getTodayLocalDateString()

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const userData = await authService.getMe()
        setUser(userData)
        const predictionData = await authService.getPredictions(todayStr)
        setPrediction(predictionData)
      } catch (err: any) {
        setError('Session expired. Please log in again.')
        authService.clearToken()
        setTimeout(() => navigate('/login'), 2000)
      } finally {
        setIsLoading(false)
      }
    }

    if (!authService.isAuthenticated()) {
      navigate('/login')
    } else {
      fetchDashboardData()
    }
  }, [navigate, todayStr])

  const handleLogout = () => {
    authService.clearToken()
    navigate('/login')
  }

  const getDaysUntilText = (): string => {
    if (!prediction || !prediction.predicted_next_period_start) return ''
    const target = parseLocalDate(prediction.predicted_next_period_start)
    const today = parseLocalDate(todayStr)
    const diffTime = target.getTime() - today.getTime()
    const days = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    if (days > 0) return `Next period in ${days} ${days === 1 ? 'day' : 'days'}`
    if (days === 0) return 'Next period predicted today! 🌸'
    return `Next period predicted ${Math.abs(days)} ${Math.abs(days) === 1 ? 'day' : 'days'} ago`
  }

  if (isLoading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading your cycle summary...</p>
      </div>
    )
  }

  const hasPredictions = prediction && prediction.predicted_next_period_start !== null
  const daysUntilText = getDaysUntilText()

  return (
    <div className="dashboard-container">
      {/* Auto-triggered notification opt-in prompt (shows after first cycle) */}
      <NotificationPrompt
        forceOpen={showNotifPrompt}
        onRequestClose={() => setShowNotifPrompt(false)}
      />

      <header className="dashboard-header">
        <div className="logo-group" onClick={() => navigate('/home')} style={{ cursor: 'pointer' }}>
          <span className="logo-emoji">🌸</span>
          <span className="logo-text">period.</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {user && (
            <span style={{ fontSize: '14px', color: 'var(--text-muted)', fontWeight: 500 }}>
              {user.email}
            </span>
          )}
          <button onClick={handleLogout} className="btn btn-secondary">
            Log Out
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        {error ? (
          <div className="auth-error-banner" role="alert">
            <span>{error}</span>
          </div>
        ) : (
          <div className="welcome-card dashboard-summary-card">
            {hasPredictions && prediction ? (
              <div className="cycle-summary-active">
                <h1 className="dashboard-greeting">Hello!</h1>
                <p className="subtitle">Here is your current cycle summary.</p>

                <div className="cycle-highlight-ring">
                  <div className="ring-content">
                    <span className="ring-cycle-label">Cycle Day</span>
                    <span className="ring-cycle-value">
                      {prediction.current_cycle_day ?? '—'}
                    </span>
                  </div>
                </div>

                <div className="countdown-summary-text">
                  <h3>{daysUntilText}</h3>
                </div>

                <div className="prediction-meta-grid">
                  <div className="meta-box">
                    <span className="meta-label">Basis</span>
                    <span className="meta-value">
                      {prediction.basis.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="meta-box">
                    <span className="meta-label">Confidence</span>
                    <span className={`meta-value confidence-badge confidence-${prediction.confidence}`}>
                      {prediction.confidence}
                    </span>
                  </div>
                  <div className="meta-box">
                    <span className="meta-label">Avg. Cycle</span>
                    <span className="meta-value">
                      {Math.round(prediction.average_cycle_length)} days
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="cycle-summary-onboarding">
                <span className="onboarding-welcome-emoji">🌸</span>
                <h1 className="dashboard-greeting">Welcome!</h1>
                <p className="subtitle">Log your first period to get started.</p>
                <div className="placeholder-info onboarding-info-card">
                  <span className="info-icon">💡</span>
                  <p>
                    Once you record a period, we will calculate your cycle length
                    and estimate your next period timeline.
                  </p>
                </div>
              </div>
            )}

            {/* Shortcut Buttons */}
            <div className="dashboard-shortcut-buttons">
              <button
                onClick={() => navigate('/log-period')}
                className="btn btn-primary"
                style={{ width: '100%', display: 'flex', gap: '10px', justifyContent: 'center', alignItems: 'center' }}
              >
                <span>➕</span> Log Period
              </button>
              <button
                onClick={() => navigate('/calendar')}
                className="btn btn-secondary"
                style={{ width: '100%', display: 'flex', gap: '10px', justifyContent: 'center', alignItems: 'center' }}
              >
                <span>📅</span> View Calendar
              </button>
            </div>

            {/* Notification card — status-only, no toggle. Full control in /settings/notifications */}
            <div className="notif-settings-card">
              <div className="notif-settings-header">
                <span className="notif-settings-icon">🔔</span>
                <div>
                  <div className="notif-settings-title">Notifications</div>
                  <div className="notif-settings-subtitle">{getNotifSubtitle()}</div>
                </div>
              </div>
              <div className="notif-settings-actions">
                <button
                  onClick={() => navigate('/settings/notifications')}
                  className="btn btn-secondary notif-toggle-btn"
                  style={{ display: 'flex', gap: '4px', alignItems: 'center' }}
                  aria-label="Notification settings page"
                >
                  ⚙️ Settings
                </button>
              </div>
            </div>

            {/* Account details */}
            <details className="user-details-collapsible">
              <summary className="user-details-summary">Account Details</summary>
              <div className="user-details-box compact-details">
                <div className="detail-item">
                  <span className="label">User ID:</span>
                  <span className="value">{user?.id}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Email:</span>
                  <span className="value">{user?.email}</span>
                </div>
              </div>
            </details>
          </div>
        )}
      </main>
    </div>
  )
}
