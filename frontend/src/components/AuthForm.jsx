import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

// -----------------------------------------------------------------------
// Cedric AI - Login / Register form
// -----------------------------------------------------------------------
// One component handles both modes (toggled with `mode`) since they
// share almost all of their fields and all of their submit handling -
// splitting into two components would just duplicate that logic.
// -----------------------------------------------------------------------

export function AuthForm() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const isRegister = mode === 'register'

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (isRegister) {
        await register({ email, fullName, password })
      } else {
        await login({ email, password })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-form">
      <div className="tabs">
        <button
          type="button"
          className={`tab ${!isRegister ? 'tab-active' : ''}`}
          onClick={() => {
            setMode('login')
            setError(null)
          }}
        >
          Log in
        </button>
        <button
          type="button"
          className={`tab ${isRegister ? 'tab-active' : ''}`}
          onClick={() => {
            setMode('register')
            setError(null)
          }}
        >
          Register
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {isRegister && (
          <label className="field">
            Full name
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              minLength={1}
              maxLength={120}
              autoComplete="name"
            />
          </label>
        )}

        <label className="field">
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </label>

        <label className="field">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
          />
        </label>

        {error && <div className="form-error">{error}</div>}

        <button type="submit" className="submit-btn" disabled={submitting}>
          {submitting
            ? 'Please wait…'
            : isRegister
              ? 'Create account'
              : 'Log in'}
        </button>
      </form>
    </div>
  )
}
