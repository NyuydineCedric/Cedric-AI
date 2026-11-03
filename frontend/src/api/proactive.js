import { apiFetch } from './client'

export function getUpcomingDeadlines(token) {
  return apiFetch('/api/proactive/deadlines', { token })
}