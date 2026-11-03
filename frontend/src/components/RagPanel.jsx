import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { askDocuments } from "../api/rag";

// -----------------------------------------------------------------------
// Cedric AI - "Ask your documents" (Phase 7-9)
// -----------------------------------------------------------------------
// Unlike ChatPanel (Phase 3, general Gemini conversation), every
// answer here is either grounded in the student's own uploaded
// material with visible citations, or an honest "I don't have enough
// evidence" - never a confident-sounding guess from the model's
// general knowledge. See backend/app/services/rag.py.
// -----------------------------------------------------------------------

export function RagPanel() {
  const { token } = useAuth();
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [asking, setAsking] = useState(false);

  async function handleAsk(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking) return;

    setAsking(true);
    setError(null);
    setResult(null);
    try {
      setResult(await askDocuments(token, q));
    } catch (err) {
      setError(err.message);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="rag-panel">
      <p className="lede small">
        Answers come only from your uploaded documents, with sources. If nothing
        relevant was found, Cedric AI says so instead of guessing.
      </p>

      <form className="chat-input-row" onSubmit={handleAsk}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your documents…"
          disabled={asking}
        />
        <button
          type="submit"
          className="submit-btn"
          disabled={asking || !question.trim()}
        >
          {asking ? "Searching…" : "Ask"}
        </button>
      </form>

      {error && <div className="form-error">{error}</div>}

      {result && (
        <div className="rag-result">
          <p
            className={`rag-answer ${result.grounded ? "" : "rag-answer-ungrounded"}`}
          >
            {result.answer}
          </p>
          {result.fully_verified === false && (
            <div className="verification-warning">
              <span className="chunk-label">⚠ Possibly unsupported claims</span>
              <ul>
                {result.unsupported_claims.map((claim, i) => (
                  <li key={i}>{claim}</li>
                ))}
              </ul>
            </div>
          )}

          {result.sources.length > 0 && (
            <div className="rag-sources">
              <span className="chunk-label">Sources</span>
              {result.sources.map((s, i) => (
                <div key={i} className="rag-source">
                  <span className="document-name">
                    {s.filename}
                    {s.page_number != null && ` · page/slide ${s.page_number}`}
                    {s.section_title && ` · ${s.section_title}`}
                    {` · similarity ${(s.similarity * 100).toFixed(0)}%`}
                  </span>
                  <p>{s.snippet}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
