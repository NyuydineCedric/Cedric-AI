import { apiFetch } from './client'

// Sends the whole conversation so far and gets back Gemini's next
// reply. See backend/app/schemas/chat.py for why history isn't
// persisted server-side yet (Phase 3 is intentionally "basic").
export function sendChatMessage(token, messages) {
  return apiFetch('/api/chat/message', {
    method: 'POST',
    token,
    body: { messages },
  })
}
