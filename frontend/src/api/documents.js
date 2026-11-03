import { API_BASE_URL, apiFetch } from './client'

export function listDocuments(token) {
  return apiFetch('/api/documents', { token })
}

export function getDocumentChunks(token, documentId) {
  return apiFetch(`/api/documents/${documentId}/chunks`, { token })
}

// Phase 11: find the actual file(s) matching a natural-language
// description, e.g. "the PDF where I wrote about PID controllers."
export function searchDocuments(token, query) {
  return apiFetch('/api/documents/search', { method: 'POST', token, body: { query } })
}

// File uploads use multipart/form-data, not JSON, so this bypasses
// apiFetch's JSON body handling and calls fetch() directly - the
// browser sets the correct multipart Content-Type (with boundary)
// automatically as long as we don't set Content-Type ourselves.
export async function uploadDocument(token, file, visibility = 'personal') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('visibility', visibility)

  const res = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  })

  const data = await res.json()
  if (!res.ok) {
    throw new Error(data?.detail || `Upload failed with status ${res.status}`)
  }
  return data
}

export async function deleteDocument(token, documentId) {
  const res = await fetch(`${API_BASE_URL}/api/documents/${documentId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.detail || `Delete failed with status ${res.status}`)
  }
}

// Downloads need the auth header, so a plain <a href> won't work -
// the backend has no way to see a bearer token on a bare navigation.
// Instead we fetch the file as a blob and trigger a save via a
// temporary object URL.
export async function downloadDocument(token, documentId, filename) {
  const res = await fetch(`${API_BASE_URL}/api/documents/${documentId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    throw new Error(`Download failed with status ${res.status}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
