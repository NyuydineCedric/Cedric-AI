import { apiFetch } from './client'

// -----------------------------------------------------------------------
// Cedric AI - Quiz API (Phase 20)
// -----------------------------------------------------------------------

export async function generateQuiz(token, { topic, documentId, numQuestions, difficulty }) {
  return apiFetch('/api/quiz/generate', {
    method: 'POST',
    token,
    body: {
      topic: topic || null,
      document_id: documentId || null,
      num_questions: numQuestions,
      difficulty,
    },
  })
}

export async function recordQuizAttempt(token, { topic, documentId, difficulty, numQuestions, correctCount }) {
  return apiFetch('/api/quiz/attempts', {
    method: 'POST',
    token,
    body: {
      topic: topic || null,
      document_id: documentId || null,
      difficulty,
      num_questions: numQuestions,
      correct_count: correctCount,
    },
  })
}

export async function getQuizProgress(token) {
  return apiFetch('/api/quiz/progress', { token })
}