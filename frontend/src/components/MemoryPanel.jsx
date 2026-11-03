import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { createMemory, deleteMemory, listMemories } from "../api/memory";
import { getUpcomingDeadlines } from "../api/proactive";

// -----------------------------------------------------------------------
// Cedric AI - Memory (Phase 12)
// -----------------------------------------------------------------------
// Deliberately NOT a chat transcript. This is a short, curated list of
// facts about the student - goals, preferences, deadlines, current
// projects - that later phases (context engine, orchestrator) draw on
// to personalize responses. See backend/app/models/memory.py for the
// three-way distinction between this, RAG knowledge, and short-term
// conversation context.
// -----------------------------------------------------------------------

const CATEGORIES = ["goal", "preference", "deadline", "project", "other"];

export function MemoryPanel() {
  const { token } = useAuth();
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [category, setCategory] = useState("goal");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  async function refresh() {
    try {
      setMemories(await listMemories(token));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    const text = content.trim();
    if (!text || saving) return;

    setSaving(true);
    setError(null);
    try {
      await createMemory(token, category, text);
      setContent("");
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    setError(null);
    try {
      await deleteMemory(token, id);
      setMemories((items) => items.filter((m) => m.id !== id));
    } catch (err) {
      setError(err.message);
    }
  }

  const [deadlines, setDeadlines] = useState([]);

  useEffect(() => {
    getUpcomingDeadlines(token)
      .then(setDeadlines)
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  {
    deadlines.length > 0 && (
      <div className="deadline-banner">
        <span className="chunk-label">Coming up</span>
        {deadlines.map((d) => (
          <div key={d.memory_id} className="deadline-row">
            <span className="document-name">{d.label}</span>
            <span className="document-meta">
              {d.date} ·{" "}
              {d.days_remaining < 0
                ? "past"
                : d.days_remaining === 0
                  ? "today"
                  : `in ${d.days_remaining} day${d.days_remaining === 1 ? "" : "s"}`}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="memory-panel">
      <p className="lede small">
        A short list of things worth remembering about you - not a transcript of
        every conversation.
      </p>

      <form className="memory-form" onSubmit={handleAdd}>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="e.g. Final exam for EEE301 is on Dec 12"
          disabled={saving}
        />
        <button
          type="submit"
          className="submit-btn"
          disabled={saving || !content.trim()}
        >
          Add
        </button>
      </form>

      {error && <div className="form-error">{error}</div>}

      {loading ? (
        <p className="lede small">Loading…</p>
      ) : memories.length === 0 ? (
        <p className="chat-empty">Nothing remembered yet.</p>
      ) : (
        <ul className="document-list">
          {memories.map((m) => (
            <li key={m.id} className="document-row">
              <div className="document-info">
                <span className="status-pill status-pill-completed">
                  {m.category}
                </span>
                <span className="document-name">{m.content}</span>
              </div>
              <div className="document-actions">
                <button
                  type="button"
                  className="link-btn danger"
                  onClick={() => handleDelete(m.id)}
                >
                  Forget
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
