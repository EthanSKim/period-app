import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authService } from '../api'
import type { User, PredictionResponse } from '../api'

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

export const Home: React.FC = () => {
  const [user, setUser] = useState<User | null>(null)
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const todayStr = getTodayLocalDateString()

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const userData = await authService.getMe()
        setUser(userData)

        // Fetch predictions relative to today
        const predictionData = await authService.getPredictions(todayStr)
        setPrediction(predictionData)
      } catch (err: any) {
        setError('Session expired. Please log in again.')
        authService.clearToken()
        setTimeout(() => {
          navigate('/login')
        }, 2000)
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

  // Get localized days until text for the dashboard
  const getDaysUntilText = (): string => {
    if (!prediction || !prediction.predicted_next_period_start) return ''
    const target = parseLocalDate(prediction.predicted_next_period_start)
    const today = parseLocalDate(todayStr)
    const diffTime = target.getTime() - today.getTime()
    const days = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

    if (days > 0) {
      return `Next period in ${days} ${days === 1 ? 'day' : 'days'}`
    } else if (days === 0) {
      return 'Next period predicted today! 🌸'
    } else {
      return `Next period predicted ${Math.abs(days)} ${Math.abs(days) === 1 ? 'day' : 'days'} ago`
    }
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
              // Case: Logged cycle prediction active
              <div className="cycle-summary-active">
                <h1 className="dashboard-greeting">Hello!</h1>
                <p className="subtitle">Here is your current cycle summary.</p>

                {/* Big Visual Ring / Ring Card */}
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

                {/* Grid details */}
                <div className="prediction-meta-grid">
                  <div className="meta-box">
                    <span className="meta-label">Basis</span>
                    <span className="meta-value">
                      {prediction.basis.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="meta-box">
                    <span className="meta-label">Confidence</span>
                    <span
                      className={`meta-value confidence-badge confidence-${prediction.confidence}`}
                    >
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
              // Case: No cycles logged yet -> Onboarding
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
                style={{
                  width: '100%',
                  display: 'flex',
                  gap: '10px',
                  justifyContent: 'center',
                  alignItems: 'center',
                }}
              >
                <span>➕</span> Log Period
              </button>
              <button
                onClick={() => navigate('/calendar')}
                className="btn btn-secondary"
                style={{
                  width: '100%',
                  display: 'flex',
                  gap: '10px',
                  justifyContent: 'center',
                  alignItems: 'center',
                }}
              >
                <span>📅</span> View Calendar
              </button>
            </div>

            {/* Secondary collapsible user account detail box */}
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
