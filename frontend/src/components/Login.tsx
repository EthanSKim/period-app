import React, { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authService } from '../api'

export const Login: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (authService.isAuthenticated()) {
      navigate('/home')
    }
  }, [navigate])

  const validateEmail = (emailStr: string) => {
    return /\S+@\S+\.\S+/.test(emailStr)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Clientside validations
    if (!email.trim() || !password.trim()) {
      setError('Please fill in all fields.')
      return
    }

    if (!validateEmail(email)) {
      setError('Please enter a valid email address.')
      return
    }

    setIsLoading(true)
    try {
      await authService.login(email.trim(), password)
      navigate('/home')
    } catch (err: unknown) {
      // Show user-friendly error message, masking raw API messages if they are not user friendly
      const msg = err instanceof Error ? err.message : String(err)
      if (
        msg.includes('401') ||
        msg.toLowerCase().includes('unauthorized') ||
        msg.toLowerCase().includes('incorrect')
      ) {
        setError('Incorrect email or password.')
      } else {
        setError('Login failed. Please check your credentials and try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-logo">🌸</div>
          <h2>period.</h2>
          <p>Sign in to your cycle workspace</p>
        </div>

        {error && (
          <div className="auth-error-banner" role="alert">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              type="email"
              id="email"
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="spinner-container">
                <span className="spinner"></span>
                <span>Signing in...</span>
              </span>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            Don't have an account?{' '}
            <Link to="/register" className="auth-link">
              Create an account
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
