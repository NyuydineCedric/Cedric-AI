import { createContext, useContext, useEffect, useState } from 'react'
import { apiFetch } from '../api/client'

// -----------------------------------------------------------------------
// Cedric AI - Auth Context
// -----------------------------------------------------------------------
// React Context lets any component in the tree read "who is logged
// in" and call login/register/logout, without threading props down
// through every intermediate component by hand.
//
// TOKEN STORAGE DECISION:
// The JWT is kept in `localStorage` under `cedric_token`. This is the
// simplest option and fine for this stage of the project, but it has
// a real tradeoff worth knowing: any JavaScript that runs on this
// page (including an injected XSS payload, if one ever existed) can
// read localStorage and steal the token. The more locked-down
// alternative is an httpOnly cookie, which JavaScript can't read at
// all - but that requires the backend to set cookies and adds CSRF
// protection to think about. We're deliberately deferring that
// tradeoff to Phase 27 (security hardening), once there's more
// surface area to justify it.
// -----------------------------------------------------------------------

const TOKEN_STORAGE_KEY = 'cedric_token'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY))
  const [user, setUser] = useState(null)
  // 'loading' while we check an existing token, 'ready' once resolved.
  const [status, setStatus] = useState('loading')

  // On first load, if a token was saved from a previous visit, ask the
  // backend who it belongs to. This is what keeps a user logged in
  // across page refreshes without re-entering their password.
  useEffect(() => {
    if (!token) {
      setStatus('ready')
      return
    }

    apiFetch('/api/auth/me', { token })
      .then((profile) => {
        setUser(profile)
        setStatus('ready')
      })
      .catch(() => {
        // Token expired, was revoked, or the user no longer exists -
        // clear it so we don't keep retrying a dead token.
        localStorage.removeItem(TOKEN_STORAGE_KEY)
        setToken(null)
        setUser(null)
        setStatus('ready')
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function register({ email, fullName, password }) {
    await apiFetch('/api/auth/register', {
      method: 'POST',
      body: { email, full_name: fullName, password },
    })
    // Registration doesn't log the user in automatically - reuse the
    // same login() flow so there's exactly one code path that issues
    // and stores a token.
    await login({ email, password })
  }

  async function login({ email, password }) {
    const { access_token: accessToken } = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: { email, password },
    })
    const profile = await apiFetch('/api/auth/me', { token: accessToken })

    localStorage.setItem(TOKEN_STORAGE_KEY, accessToken)
    setToken(accessToken)
    setUser(profile)
  }

  function logout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    setToken(null)
    setUser(null)
  }

  const value = {
    token,
    user,
    isAuthenticated: Boolean(user),
    isLoading: status === 'loading',
    register,
    login,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used inside an <AuthProvider>')
  }
  return ctx
}
