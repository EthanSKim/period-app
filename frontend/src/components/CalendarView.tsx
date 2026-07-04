import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authService } from '../api'
import type { User, Cycle, PredictionResponse } from '../api'

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

const getYYYYMMDD = (d: Date): string => {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const formatMonthYear = (d: Date): string => {
  return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

export const CalendarView: React.FC = () => {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [cycles, setCycles] = useState<Cycle[]>([])
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null)
  // Calendar states
  const [currentMonthDate, setCurrentMonthDate] = useState<Date>(new Date())
  const [selectedDate, setSelectedDate] = useState<Date>(new Date())

  // Loading & Error states
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const todayStr = getTodayLocalDateString()

  useEffect(() => {
    const initData = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const userData = await authService.getMe()
        setUser(userData)

        const [cyclesData, predictionData] = await Promise.all([
          authService.getCycles(),
          authService.getPredictions(todayStr),
        ])
        setCycles(cyclesData)
        setPrediction(predictionData)
      } catch (err: any) {
        if (!authService.isAuthenticated()) {
          setError('Session expired. Please log in again.')
          authService.clearToken()
          setTimeout(() => navigate('/login'), 2000)
        } else {
          setError(err.message || 'Failed to retrieve data.')
        }
      } finally {
        setIsLoading(false)
      }
    }

    if (!authService.isAuthenticated()) {
      navigate('/login')
    } else {
      initData()
    }
  }, [navigate, todayStr])

  // Navigation handlers for months
  const handlePrevMonth = () => {
    setCurrentMonthDate(
      new Date(currentMonthDate.getFullYear(), currentMonthDate.getMonth() - 1, 1)
    )
  }

  const handleNextMonth = () => {
    setCurrentMonthDate(
      new Date(currentMonthDate.getFullYear(), currentMonthDate.getMonth() + 1, 1)
    )
  }

  const handleResetToToday = () => {
    const today = new Date()
    setCurrentMonthDate(today)
    setSelectedDate(today)
  }

  // Helper to check what events occur on a given date
  const getDateInfo = (d: Date) => {
    const dStr = getYYYYMMDD(d)
    const isToday = dStr === todayStr

    // Check logged period
    let loggedCycle: Cycle | null = null
    let loggedDayIndex: number | null = null

    for (const cycle of cycles) {
      const startStr = cycle.start_date
      const endStr = cycle.end_date

      if (endStr) {
        if (dStr >= startStr && dStr <= endStr) {
          loggedCycle = cycle
          const diffTime = d.getTime() - parseLocalDate(startStr).getTime()
          loggedDayIndex = Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1
          break
        }
      } else {
        // Ongoing period
        if (dStr >= startStr && dStr <= todayStr) {
          loggedCycle = cycle
          const diffTime = d.getTime() - parseLocalDate(startStr).getTime()
          loggedDayIndex = Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1
          break
        }
      }
    }

    // Check predicted period range
    let predictedDayIndex: number | null = null
    if (prediction && prediction.predicted_next_period_start) {
      const predStart = parseLocalDate(prediction.predicted_next_period_start)
      const predEnd = new Date(predStart)
      predEnd.setDate(
        predEnd.getDate() + Math.round(prediction.average_cycle_length) - 1
      )

      if (d >= predStart && d <= predEnd) {
        const diffTime = d.getTime() - predStart.getTime()
        predictedDayIndex = Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1
      }
    }

    // Check fertile window
    let isFertile = false
    if (prediction && prediction.fertile_window_start && prediction.fertile_window_end) {
      isFertile = dStr >= prediction.fertile_window_start && dStr <= prediction.fertile_window_end
    }

    // Check ovulation day
    let isOvulation = false
    if (prediction && prediction.predicted_ovulation_date) {
      isOvulation = dStr === prediction.predicted_ovulation_date
    }

    return {
      isToday,
      loggedCycle,
      loggedDayIndex,
      predictedDayIndex,
      isFertile,
      isOvulation,
    }
  }

  // Generate calendar grid dates
  const generateGridDates = (): Date[] => {
    const year = currentMonthDate.getFullYear()
    const month = currentMonthDate.getMonth()

    const firstDayOfMonth = new Date(year, month, 1)
    const startDayOfWeek = firstDayOfMonth.getDay() // 0 = Sunday, etc.
    const totalDaysInMonth = new Date(year, month + 1, 0).getDate()
    const prevMonthDays = new Date(year, month, 0).getDate()

    const grid: Date[] = []

    // Previous month padding
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      grid.push(new Date(year, month - 1, prevMonthDays - i))
    }

    // Current month days
    for (let i = 1; i <= totalDaysInMonth; i++) {
      grid.push(new Date(year, month, i))
    }

    // Next month padding (complete grid of 42 cells)
    const totalCells = 42
    const nextPadding = totalCells - grid.length
    for (let i = 1; i <= nextPadding; i++) {
      grid.push(new Date(year, month + 1, i))
    }

    return grid
  }

  // Get localized days until text for the banner
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
      return `Period predicted ${Math.abs(days)} ${Math.abs(days) === 1 ? 'day' : 'days'} ago`
    }
  }

  // Format dates for readability in detail card
  const formatDetailDate = (d: Date): string => {
    return d.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    })
  }

  if (isLoading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading your cycle calendar...</p>
      </div>
    )
  }

  const gridDates = generateGridDates()
  const selectedInfo = getDateInfo(selectedDate)
  const daysUntilText = getDaysUntilText()

  const hasPredictions = prediction && prediction.predicted_next_period_start !== null

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
          <button onClick={() => navigate('/log-period')} className="btn btn-secondary">
            📅 Log Period
          </button>
          <button onClick={() => navigate('/home')} className="btn btn-secondary">
            Back to Home
          </button>
        </div>
      </header>

      <main className="dashboard-main-scroller">
        <div className="log-screen-wrapper">
          {error && (
            <div className="auth-error-banner" role="alert">
              <span className="error-icon">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* Prediction Summary Banner */}
          {hasPredictions && prediction ? (
            <div className="prediction-banner" role="status" aria-live="polite">
              <div className="banner-content">
                <span className="banner-emoji">✨</span>
                <span className="banner-title-text">
                  Cycle Day {prediction.current_cycle_day ?? '—'} &middot; {daysUntilText}
                </span>
              </div>
              <div className="banner-pills">
                <span className="pill-badge-basis">
                  Basis: {prediction.basis.replace('_', ' ')}
                </span>
                <span className={`pill-badge-confidence confidence-${prediction.confidence}`}>
                  Confidence: {prediction.confidence}
                </span>
              </div>
            </div>
          ) : (
            <div className="prediction-banner empty-banner" role="status" aria-live="polite">
              <span className="banner-emoji">💡</span>
              <span className="banner-title-text">
                Log your first period to start predictions
              </span>
            </div>
          )}

          <div className="log-grid">
            {/* Calendar Column */}
            <div className="log-card">
              <div className="calendar-header-controls">
                <h2 className="calendar-month-title">
                  {formatMonthYear(currentMonthDate)}
                </h2>
                <div className="calendar-nav-buttons">
                  <button onClick={handlePrevMonth} className="btn-nav" aria-label="Previous Month">
                    &larr;
                  </button>
                  <button onClick={handleResetToToday} className="btn-nav btn-nav-today">
                    Today
                  </button>
                  <button onClick={handleNextMonth} className="btn-nav" aria-label="Next Month">
                    &rarr;
                  </button>
                </div>
              </div>

              {/* Calendar Grid */}
              <div className="calendar-grid-wrapper">
                {/* Weekday headers */}
                <div className="calendar-weekdays">
                  {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
                    <div key={d} className="weekday-header">
                      {d}
                    </div>
                  ))}
                </div>

                {/* Day cells */}
                <div className="calendar-days-grid">
                  {gridDates.map((date, idx) => {
                    const info = getDateInfo(date)
                    const isOutside = date.getMonth() !== currentMonthDate.getMonth()
                    const isSelected = getYYYYMMDD(date) === getYYYYMMDD(selectedDate)

                    let dayClasses = 'calendar-day-cell'
                    if (isOutside) dayClasses += ' outside'
                    if (info.isToday) dayClasses += ' today'
                    if (info.loggedCycle) dayClasses += ' logged'
                    if (info.predictedDayIndex) dayClasses += ' predicted'
                    if (info.isFertile) dayClasses += ' fertile'
                    if (info.isOvulation) dayClasses += ' ovulation'
                    if (isSelected) dayClasses += ' selected'

                    return (
                      <button
                        key={idx}
                        className={dayClasses}
                        onClick={() => setSelectedDate(date)}
                        aria-label={`${formatDetailDate(date)}${info.isToday ? ' (Today)' : ''}${info.loggedCycle ? ', Logged Period' : ''}${info.predictedDayIndex ? ', Predicted Period' : ''}${info.isFertile ? ', Fertile Window' : ''}${info.isOvulation ? ', Ovulation Day' : ''}`}
                      >
                        <div className="day-cell-top">
                          <span className="day-number-label">{date.getDate()}</span>
                          <div className="day-cell-badge-container">
                            {info.isOvulation && (
                              <span className="ovulation-egg-badge" title="Predicted Ovulation Day">
                                🥚
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="day-indicators-container">
                          {info.isToday && <span className="indicator-dot today-dot"></span>}
                          {info.loggedCycle && <span className="indicator-dot logged-dot"></span>}
                          {info.predictedDayIndex && <span className="indicator-dot predicted-dot"></span>}
                          {info.isFertile && <span className="indicator-dot fertile-dot"></span>}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Color legend */}
              <div className="calendar-legend">
                <div className="legend-item">
                  <span className="legend-swatch logged-swatch"></span>
                  <span className="legend-label">Logged Period</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch predicted-swatch"></span>
                  <span className="legend-label">Predicted Period</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch fertile-swatch"></span>
                  <span className="legend-label">Fertile Window</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch ovulation-swatch">🥚</span>
                  <span className="legend-label">Ovulation Day</span>
                </div>
              </div>
            </div>

            {/* Details Column */}
            <div className="log-card flex-column">
              <h2 className="card-title">🗓️ Day Details</h2>
              <p className="card-subtitle">{formatDetailDate(selectedDate)}</p>

              <div className="day-details-panel">
                {selectedInfo.isToday && (
                  <div className="detail-status-row highlight-row">
                    <span className="status-emoji">🌟</span>
                    <div>
                      <div className="status-title">Today</div>
                      <div className="status-desc">This is the current day.</div>
                    </div>
                  </div>
                )}

                {selectedInfo.loggedCycle && (
                  <div className="detail-status-row logged-row">
                    <span className="status-emoji">🩸</span>
                    <div>
                      <div className="status-title">
                        Logged Period: Day {selectedInfo.loggedDayIndex}
                      </div>
                      <div className="status-desc">
                        Cycle started on {selectedInfo.loggedCycle.start_date}
                        {selectedInfo.loggedCycle.end_date
                          ? ` and ended on ${selectedInfo.loggedCycle.end_date}.`
                          : ' and is currently ongoing.'}
                      </div>
                      {selectedInfo.loggedCycle.cycle_length && (
                        <div className="status-meta">
                          Total cycle length: {selectedInfo.loggedCycle.cycle_length} days.
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {selectedInfo.predictedDayIndex && (
                  <div className="detail-status-row predicted-row">
                    <span className="status-emoji">🔮</span>
                    <div>
                      <div className="status-title">
                        Predicted Period Day {selectedInfo.predictedDayIndex}
                      </div>
                      <div className="status-desc">
                        Calculated based on your historical cycle data.
                      </div>
                      {prediction && (
                        <div className="status-meta">
                          Predicted next period start: {prediction.predicted_next_period_start} <br />
                          Average cycle length: {Math.round(prediction.average_cycle_length)} days.
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {selectedInfo.isFertile && (
                  <div className="detail-status-row fertile-row">
                    <span className="status-emoji">🌱</span>
                    <div>
                      <div className="status-title">Fertile Window</div>
                      <div className="status-desc">
                        Days where pregnancy is most likely to occur.
                      </div>
                      {prediction && (
                        <div className="status-meta">
                          Fertile range: {prediction.fertile_window_start} to {prediction.fertile_window_end}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {selectedInfo.isOvulation && (
                  <div className="detail-status-row ovulation-row">
                    <span className="status-emoji">🥚</span>
                    <div>
                      <div className="status-title">Predicted Ovulation Day</div>
                      <div className="status-desc">
                        Estimated release of the egg, typically the peak day of the fertile window.
                      </div>
                    </div>
                  </div>
                )}

                {!selectedInfo.loggedCycle &&
                  !selectedInfo.predictedDayIndex &&
                  !selectedInfo.isFertile &&
                  !selectedInfo.isOvulation && (
                    <div className="detail-status-row empty-row">
                      <span className="status-emoji">🌿</span>
                      <div>
                        <div className="status-title">No Cycle Events</div>
                        <div className="status-desc">
                          No period is logged or predicted, and no symptoms are recorded.
                        </div>
                      </div>
                    </div>
                  )}
              </div>

              {/* Quick actions box */}
              <div className="details-quick-actions">
                <h4>Quick Actions</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <button
                    onClick={() => navigate('/log-period')}
                    className="btn btn-primary"
                    style={{ width: '100%' }}
                  >
                    ➕ Log Period Dates
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

    </div>
  )
}
