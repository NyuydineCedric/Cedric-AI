import { apiFetch } from './client'

// Phase 14-15: Gemini itself decides whether to answer directly or
// call a tool first (search files, ask documents, read/save memory).
export function sendOrchestratedMessage(token, messages) {
  return apiFetch('/api/orchestrator/chat', {
    method: 'POST',
    token,
    body: { messages },
  })
}
