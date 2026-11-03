import { apiFetch } from './client'

// Grounded Q&A over the student's own documents (Phase 7-9) - distinct
// from the free-form chat in api/chat.js, which uses the model's
// general knowledge with no retrieval or citations.
export function askDocuments(token, question) {
  return apiFetch('/api/rag/ask', {
    method: 'POST',
    token,
    body: { question },
  })
}
