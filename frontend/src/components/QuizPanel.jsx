import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";

import { listDocuments } from "../api/documents";
import { generateQuiz, getQuizProgress, recordQuizAttempt } from "../api/quiz";

// -----------------------------------------------------------------------
// Cedric AI - Quiz / Study Coach (Phase 20)
// -----------------------------------------------------------------------
// Two quiz sources: a free-text topic, or one of the student's own
// processed documents (grounded - see services/quiz.py). Grading
// happens entirely client-side once the questions arrive, since
// correct_index is already part of the response - no extra backend
// round-trip needed just to check an answer.
// -----------------------------------------------------------------------

const DIFFICULTIES = ["easy", "medium", "hard"];

export function QuizPanel() {
  const { token } = useAuth();
  const [mode, setMode] = useState("topic"); // 'topic' | 'document'
  const [topic, setTopic] = useState("");
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState("");
  const [numQuestions, setNumQuestions] = useState(5);
  const [difficulty, setDifficulty] = useState("medium");

  const [questions, setQuestions] = useState(null);
  const [answers, setAnswers] = useState({}); // { [questionIndex]: selectedOptionIndex }
  const [submitted, setSubmitted] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const [progress, setProgress] = useState([]);

  useEffect(() => {
    getQuizProgress(token)
      .catch(() => {})
      .then((p) => p && setProgress(p));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    listDocuments(token)
      .then((docs) =>
        setDocuments(docs.filter((d) => d.processing_status === "completed")),
      )
      .catch(() => {
        // Non-fatal: the topic-based mode still works without this list.
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleGenerate(e) {
    e.preventDefault();
    if (generating) return;
    if (mode === "topic" && !topic.trim()) return;
    if (mode === "document" && !documentId) return;

    setGenerating(true);
    setError(null);
    setQuestions(null);
    setAnswers({});
    setSubmitted(false);

    try {
      const result = await generateQuiz(token, {
        topic: mode === "topic" ? topic.trim() : null,
        documentId: mode === "document" ? Number(documentId) : null,
        numQuestions,
        difficulty,
      });
      setQuestions(result.questions);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  function selectAnswer(questionIndex, optionIndex) {
    if (submitted) return;
    setAnswers((prev) => ({ ...prev, [questionIndex]: optionIndex }));
  }

  const allAnswered =
    questions && questions.every((_, i) => answers[i] !== undefined);
  const score = questions
    ? questions.reduce(
        (sum, q, i) => sum + (answers[i] === q.correct_index ? 1 : 0),
        0,
      )
    : 0;

  return (
    <div className="quiz-panel">
      <p className="lede small">
        Generate a quiz from a topic, or from one of your own processed
        documents - questions come straight from Gemini, checked before they
        reach you.
      </p>

      {progress.length > 0 && (
        <div className="quiz-progress">
          <span className="chunk-label">Your progress</span>
          {progress.map((p, i) => (
            <button
              type="button"
              key={i}
              className="quiz-progress-row"
              onClick={() => {
                if (p.topic) {
                  setMode("topic");
                  setTopic(p.topic);
                } else if (p.document_id) {
                  setMode("document");
                  setDocumentId(String(p.document_id));
                }
                setDifficulty(
                  p.suggested_difficulty === "harder"
                    ? "hard"
                    : p.suggested_difficulty === "easier"
                      ? "easy"
                      : difficulty,
                );
              }}
            >
              <span className="document-name">
                {p.topic || p.document_filename}
              </span>
              <span className="document-meta">
                {p.attempts} attempt{p.attempts !== 1 ? "s" : ""} · avg{" "}
                {(p.average_score * 100).toFixed(0)}% · suggest{" "}
                {p.suggested_difficulty === "same"
                  ? "same difficulty"
                  : `going ${p.suggested_difficulty}`}
              </span>
            </button>
          ))}
        </div>
      )}

      <form className="quiz-form" onSubmit={handleGenerate}>
        <div className="tabs">
          <button
            type="button"
            className={`tab ${mode === "topic" ? "tab-active" : ""}`}
            onClick={() => setMode("topic")}
          >
            From a topic
          </button>
          <button
            type="button"
            className={`tab ${mode === "document" ? "tab-active" : ""}`}
            onClick={() => setMode("document")}
          >
            From a document
          </button>
        </div>

        {mode === "topic" ? (
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Newton's laws of motion"
            disabled={generating}
          />
        ) : documents.length === 0 ? (
          <p className="lede small">
            No processed documents yet - upload one in the Documents tab first.
          </p>
        ) : (
          <select
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            disabled={generating}
          >
            <option value="">Choose a document…</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename}
              </option>
            ))}
          </select>
        )}

        <div className="quiz-options-row">
          <label>
            Questions
            <input
              type="number"
              min={1}
              max={15}
              value={numQuestions}
              onChange={(e) => setNumQuestions(Number(e.target.value))}
              disabled={generating}
            />
          </label>
          <label>
            Difficulty
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              disabled={generating}
            >
              {DIFFICULTIES.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button type="submit" className="submit-btn" disabled={generating}>
          {generating ? "Generating…" : "Generate quiz"}
        </button>
      </form>

      {error && <div className="form-error">{error}</div>}

      {questions && (
        <div className="quiz-questions">
          {questions.map((q, qi) => {
            const selected = answers[qi];
            return (
              <div key={qi} className="quiz-question">
                <p className="quiz-question-text">
                  {qi + 1}. {q.question}
                </p>
                <div className="quiz-option-list">
                  {q.options.map((option, oi) => {
                    let stateClass = "";
                    if (submitted) {
                      if (oi === q.correct_index)
                        stateClass = "quiz-option-correct";
                      else if (oi === selected)
                        stateClass = "quiz-option-incorrect";
                    } else if (oi === selected) {
                      stateClass = "quiz-option-selected";
                    }
                    return (
                      <button
                        type="button"
                        key={oi}
                        className={`quiz-option ${stateClass}`}
                        onClick={() => selectAnswer(qi, oi)}
                        disabled={submitted}
                      >
                        {option}
                      </button>
                    );
                  })}
                </div>
                {submitted && (
                  <p className="quiz-explanation">{q.explanation}</p>
                )}
              </div>
            );
          })}

          {!submitted ? (
            <button
              type="button"
              className="submit-btn"
              disabled={!allAnswered}
              onClick={() => {
                setSubmitted(true);
                recordQuizAttempt(token, {
                  topic: mode === "topic" ? topic.trim() : null,
                  documentId: mode === "document" ? Number(documentId) : null,
                  difficulty,
                  numQuestions: questions.length,
                  correctCount: score,
                })
                  .then(() => getQuizProgress(token).then(setProgress))
                  .catch(() => {
                    // Recording failure shouldn't block seeing your results -
                    // the quiz itself already succeeded.
                  });
              }}
            >
              Submit answers
            </button>
          ) : (
            <p className="quiz-score">
              Score: {score} / {questions.length}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
