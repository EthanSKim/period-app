import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authService } from '../api'
import type { User, Cycle } from '../api'

const getTodayLocalDateString = (): string => {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return 'In progress'
  try {
    // Append T00:00:00 to parse in local time and avoid timezone offset shift
    const date = new Date(dateStr + 'T00:00:00')
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export const LogPeriod: React.FC = () => {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [cycles, setCycles] = useState<Cycle[]>([])

  // Loading & Error states
  const [isLoadingUser, setIsLoadingUser] = useState(true)
  const [isLoadingCycles, setIsLoadingCycles] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [listError, setListError] = useState<string | null>(null)

  // Form states
  const [startDate, setStartDate] = useState<string>(getTodayLocalDateString())
  const [endDate, setEndDate] = useState<string>('')
  const [editingCycleId, setEditingCycleId] = useState<number | null>(null)

  const fetchCycles = async () => {
    setIsLoadingCycles(true)
    setListError(null)
    try {
      const data = await authService.getCycles()
      // Sort cycles by start date descending (newest first)
      const sorted = [...data].sort((a, b) =>
        b.start_date.localeCompare(a.start_date),
      )
      setCycles(sorted)
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : 'Failed to load cycles.'
      setListError(errorMsg)
    } finally {
      setIsLoadingCycles(false)
    }
  }

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const userData = await authService.getMe()
        setUser(userData)
        fetchCycles()
      } catch {
        setError('Session expired. Please log in again.')
        authService.clearToken()
        setTimeout(() => {
          navigate('/login')
        }, 2000)
      } finally {
        setIsLoadingUser(false)
      }
    }

    if (!authService.isAuthenticated()) {
      navigate('/login')
    } else {
      fetchUser()
    }
  }, [navigate])

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setStartDate(e.target.value)
    setValidationError(null)
    setSuccessMessage(null)
  }

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEndDate(e.target.value)
    setValidationError(null)
    setSuccessMessage(null)
  }

  const handleEditClick = (cycle: Cycle) => {
    setEditingCycleId(cycle.id)
    setStartDate(cycle.start_date)
    setEndDate(cycle.end_date || '')
    setValidationError(null)
    setSuccessMessage(null)
    setError(null)
  }

  const handleCancelEdit = () => {
    setEditingCycleId(null)
    setStartDate(getTodayLocalDateString())
    setEndDate('')
    setValidationError(null)
    setSuccessMessage(null)
    setError(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)
    setError(null)
    setSuccessMessage(null)

    // Validation
    if (!startDate) {
      setValidationError('Start date is required.')
      return
    }

    if (endDate && endDate < startDate) {
      setValidationError('End date cannot be before the start date.')
      return
    }

    setIsSaving(true)
    try {
      if (editingCycleId !== null) {
        await authService.updateCycle(editingCycleId, {
          start_date: startDate,
          end_date: endDate || null,
        })
        setSuccessMessage('Period updated successfully!')
        handleCancelEdit()
      } else {
        await authService.createCycle({
          start_date: startDate,
          end_date: endDate || null,
        })
        setSuccessMessage('Period logged successfully!')
        // Reset form to defaults
        setStartDate(getTodayLocalDateString())
        setEndDate('')
      }
      // Refresh the cycle list
      fetchCycles()
    } catch (err) {
      const errorMsg =
        err instanceof Error
          ? err.message
          : 'Failed to save cycle. Please try again.'
      setError(errorMsg)
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoadingUser) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Verifying authentication...</p>
      </div>
    )
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div
          className="logo-group"
          onClick={() => navigate('/home')}
          style={{ cursor: 'pointer' }}
        >
          <span className="logo-emoji">🌸</span>
          <span className="logo-text">period.</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {user && (
            <span
              style={{
                fontSize: '14px',
                color: 'var(--text-muted)',
                fontWeight: 500,
              }}
            >
              {user.email}
            </span>
          )}
          <button
            onClick={() => navigate('/calendar')}
            className="btn btn-secondary"
          >
            📅 Calendar
          </button>
          <button
            onClick={() => navigate('/home')}
            className="btn btn-secondary"
          >
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

          {successMessage && (
            <div className="success-banner" role="alert">
              <span className="success-icon">✨</span>
              <span>{successMessage}</span>
            </div>
          )}

          <div className="log-grid">
            {/* Form Column */}
            <div className="log-card">
              <h2 className="card-title">
                {editingCycleId !== null
                  ? '✏️ Edit Period'
                  : '📅 Log New Period'}
              </h2>
              <p className="card-subtitle">
                {editingCycleId !== null
                  ? 'Update the dates for this cycle below.'
                  : 'Track your cycle by recording the dates.'}
              </p>

              <form onSubmit={handleSubmit} className="auth-form">
                <div className="form-group">
                  <label htmlFor="startDate">Start Date</label>
                  <input
                    type="date"
                    id="startDate"
                    value={startDate}
                    onChange={handleStartDateChange}
                    required
                    className={
                      validationError && !startDate ? 'input-error' : ''
                    }
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="endDate">End Date (Optional)</label>
                  <input
                    type="date"
                    id="endDate"
                    value={endDate}
                    onChange={handleEndDateChange}
                    className={
                      validationError && endDate && endDate < startDate
                        ? 'input-error'
                        : ''
                    }
                  />
                </div>

                {validationError && (
                  <div className="validation-error-msg" role="alert">
                    <span>{validationError}</span>
                  </div>
                )}

                <div className="form-actions-row">
                  <button
                    type="submit"
                    disabled={isSaving}
                    className="btn btn-primary flex-fill"
                  >
                    {isSaving ? (
                      <div className="spinner-container">
                        <div className="spinner"></div>
                        <span>Saving...</span>
                      </div>
                    ) : (
                      <span>
                        {editingCycleId !== null ? 'Save Changes' : 'Save'}
                      </span>
                    )}
                  </button>
                  {editingCycleId !== null && (
                    <button
                      type="button"
                      onClick={handleCancelEdit}
                      disabled={isSaving}
                      className="btn btn-secondary"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </form>
            </div>

            {/* List Column */}
            <div className="log-card flex-column">
              <h2 className="card-title">🌸 Logged Cycles</h2>
              <p className="card-subtitle">
                Select a cycle below to modify it.
              </p>

              {isLoadingCycles ? (
                <div className="list-loading-state">
                  <div className="spinner small-spinner"></div>
                  <p>Retrieving cycles...</p>
                </div>
              ) : listError ? (
                <div className="list-error-state">
                  <p>{listError}</p>
                  <button
                    onClick={fetchCycles}
                    className="btn btn-secondary btn-small"
                  >
                    Retry
                  </button>
                </div>
              ) : cycles.length === 0 ? (
                <div className="empty-cycles-state">
                  <span className="empty-icon">📅</span>
                  <p>No periods logged yet. Start by logging your first one!</p>
                </div>
              ) : (
                <div className="cycles-list-container">
                  {cycles.map((cycle) => (
                    <div
                      key={cycle.id}
                      className={`cycle-list-item ${editingCycleId === cycle.id ? 'editing' : ''}`}
                      onClick={() => handleEditClick(cycle)}
                      role="button"
                      tabIndex={0}
                      aria-label={`Cycle starting ${cycle.start_date}${cycle.end_date ? ` to ${cycle.end_date}` : ' (in progress)'}`}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          handleEditClick(cycle)
                        }
                      }}
                    >
                      <div className="cycle-item-left">
                        <div className="cycle-indicator-emoji">🩸</div>
                        <div className="cycle-dates">
                          <div className="date-range-text">
                            <span className="date-start">
                              {formatDate(cycle.start_date)}
                            </span>
                            <span className="date-separator">→</span>
                            <span
                              className={`date-end ${!cycle.end_date ? 'in-progress' : ''}`}
                            >
                              {cycle.end_date
                                ? formatDate(cycle.end_date)
                                : 'In progress'}
                            </span>
                          </div>
                          <div className="date-sub">
                            {cycle.end_date
                              ? 'Completed cycle'
                              : 'Ongoing period'}
                          </div>
                        </div>
                      </div>
                      <div className="cycle-item-right">
                        {cycle.cycle_length && (
                          <span className="cycle-length-badge">
                            {cycle.cycle_length}{' '}
                            {cycle.cycle_length === 1 ? 'day' : 'days'}
                          </span>
                        )}
                        <button
                          className="edit-icon-btn"
                          aria-label="Edit this cycle"
                        >
                          ✏️
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
