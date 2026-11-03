import { API_BASE_URL } from './client'

// -----------------------------------------------------------------------
// Cedric AI - Vision API (Phase 18-19)
// -----------------------------------------------------------------------
// Doesn't use apiFetch: that helper always sends JSON, but this
// endpoint needs multipart/form-data (a file), so the fetch is built
// by hand here instead - same error-handling contract as apiFetch,
// just a different request shape.
// -----------------------------------------------------------------------

export async function analyzeImage(token, file, prompt) {
  const formData = new FormData()
  formData.append('file', file)
  if (prompt) formData.append('prompt', prompt)

  const res = await fetch(`${API_BASE_URL}/api/vision/analyze`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  })

  const raw = await res.text()
  const data = raw ? JSON.parse(raw) : null

  if (!res.ok) {
    const message = data?.detail || `Request failed with status ${res.status}`
    throw new Error(message)
  }

  return data
}