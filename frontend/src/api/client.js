// -----------------------------------------------------------------------
// Cedric AI - API client
// -----------------------------------------------------------------------
// One small helper the rest of the frontend builds on: it knows the
// backend's base URL, attaches the auth token when one is available,
// and turns non-2xx responses into thrown errors with the backend's
// own error message (FastAPI puts it under `detail`).
//
// Every future feature (documents, chat, etc.) will call `apiFetch`
// instead of raw `fetch`, so auth headers and error handling stay
// consistent in one place instead of being copy-pasted everywhere.
// -----------------------------------------------------------------------

export const API_BASE_URL = 'http://localhost:8000'

export async function apiFetch(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  // Read as text first rather than trusting the content-type header:
  // a 204 No Content response (e.g. DELETE endpoints) can still carry
  // `content-type: application/json` with an empty body, and
  // res.json() throws on empty input rather than returning null.
  const raw = await res.text()
  const data = raw ? JSON.parse(raw) : null

  if (!res.ok) {
    const message = data?.detail || `Request failed with status ${res.status}`
    throw new Error(message)
  }

  return data
}
