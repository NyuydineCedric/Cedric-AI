import { apiFetch } from './client'

export function listMemories(token) {
  return apiFetch('/api/memory', { token })
}

export function createMemory(token, category, content) {
  return apiFetch('/api/memory', { method: 'POST', token, body: { category, content } })
}

export function deleteMemory(token, id) {
  return apiFetch(`/api/memory/${id}`, { method: 'DELETE', token })
}
